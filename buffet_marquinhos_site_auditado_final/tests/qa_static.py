from __future__ import annotations

import ast
import re
import shutil
import subprocess
from pathlib import Path

from jinja2 import Environment
import yaml
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
errors: list[str] = []


def require(condition: bool, message: str) -> None:
    if not condition:
        errors.append(message)


app_path = ROOT / "app.py"
app_text = app_path.read_text(encoding="utf-8")
compile(app_text, "app.py", "exec")
tree = ast.parse(app_text)

# Rotas duplicadas com o mesmo método podem mascarar endpoints e gerar 404/405 difíceis de diagnosticar.
route_signatures: set[tuple[str, str]] = set()
for node in tree.body:
    if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        continue
    for decorator in node.decorator_list:
        if not (isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Attribute)):
            continue
        if decorator.func.attr not in {"get", "post", "route"} or not decorator.args or not isinstance(decorator.args[0], ast.Constant):
            continue
        path = str(decorator.args[0].value)
        methods = [decorator.func.attr.upper()] if decorator.func.attr in {"get", "post"} else ["GET"]
        for kw in decorator.keywords:
            if kw.arg == "methods" and isinstance(kw.value, (ast.List, ast.Tuple)):
                methods = [str(v.value).upper() for v in kw.value.elts if isinstance(v, ast.Constant)]
        for method in methods:
            signature = (method, path)
            require(signature not in route_signatures, f"Rota duplicada: {method} {path}")
            route_signatures.add(signature)

# Todas as rotas administrativas que alteram dados precisam exigir login.
for node in tree.body:
    if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        continue
    route_paths = []
    has_admin_required = False
    has_post = False
    for decorator in node.decorator_list:
        if isinstance(decorator, ast.Name) and decorator.id == "admin_required":
            has_admin_required = True
        if isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Attribute):
            if decorator.func.attr in {"get", "post", "route"}:
                if decorator.args and isinstance(decorator.args[0], ast.Constant):
                    route_paths.append(str(decorator.args[0].value))
                if decorator.func.attr == "post":
                    has_post = True
                for kw in decorator.keywords:
                    if kw.arg == "methods" and isinstance(kw.value, (ast.List, ast.Tuple)):
                        if any(isinstance(v, ast.Constant) and str(v.value).upper() == "POST" for v in kw.value.elts):
                            has_post = True
    if any(path.startswith("/admin") for path in route_paths) and node.name not in {"admin_login"}:
        require(has_admin_required, f"Rota administrativa sem @admin_required: {node.name}")
    if has_post and any(path.startswith("/admin") for path in route_paths) and node.name not in {"admin_login"}:
        require(has_admin_required, f"Rota POST administrativa sem @admin_required: {node.name}")

# Todos os templates precisam ser sintaticamente válidos.
env = Environment()
for template in ROOT.glob("templates/**/*.html"):
    template_text = template.read_text(encoding="utf-8")
    env.parse(template_text)
    literal_ids = re.findall(r'\bid=["\']([A-Za-z0-9_-]+)["\']', template_text)
    duplicates = sorted({item for item in literal_ids if literal_ids.count(item) > 1})
    require(not duplicates, f"IDs HTML duplicados em {template.name}: {', '.join(duplicates)}")
    for form_match in re.finditer(r'<form\b[^>]*method=["\']post["\'][^>]*>(.*?)</form>', template_text, re.I | re.S):
        require("csrf_token" in form_match.group(1), f"Formulário POST sem CSRF: {template.name}")

# Toda chamada url_for() em template deve apontar para um endpoint existente.
endpoints = set()
for node in tree.body:
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        for decorator in node.decorator_list:
            if isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Attribute):
                if decorator.func.attr in {"get", "post", "route"}:
                    endpoints.add(node.name)

for template in ROOT.glob("templates/**/*.html"):
    text = template.read_text(encoding="utf-8")
    for endpoint in re.findall(r"url_for\(['\"]([^'\"]+)", text):
        if endpoint != "static" and endpoint not in endpoints:
            errors.append(f"Endpoint ausente: {endpoint} em {template.name}")

# Imagens estáticas citadas pelo Python precisam existir.
for filename in re.findall(r'["\']images/([^"\']+\.(?:png|jpe?g|webp))["\']', app_text):
    if not (ROOT / "static" / "images" / filename).exists():
        errors.append(f"Imagem ausente: images/{filename}")

# Todas as imagens entregues com o projeto precisam abrir de verdade.
for image_path in (ROOT / "static" / "images").glob("*"):
    if not image_path.is_file():
        continue
    try:
        with Image.open(image_path) as image:
            image.verify()
    except Exception as exc:
        errors.append(f"Imagem corrompida ou inválida: {image_path.name}: {exc}")

public = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
ids = set(re.findall(r'\bid=["\']([^"\']+)', public))
for target in re.findall(r'href=["\']#([^"\']+)', public):
    if target and target not in ids:
        errors.append(f"Âncora sem destino: #{target}")

main_js = (ROOT / "static" / "js" / "main.js").read_text(encoding="utf-8")
render_yaml = (ROOT / "render.yaml").read_text(encoding="utf-8")
try:
    render_config = yaml.safe_load(render_yaml)
    require(isinstance(render_config, dict), "render.yaml não gera um objeto YAML válido")
except yaml.YAMLError as exc:
    errors.append(f"render.yaml inválido: {exc}")
    render_config = {}
admin_menu = (ROOT / "templates" / "admin" / "menu.html").read_text(encoding="utf-8")
content_template = (ROOT / "templates" / "admin" / "content.html").read_text(encoding="utf-8")

checks = {
    "WhatsApp padrão": "5548988608441" in app_text,
    "Rota health": '@app.get("/health")' in app_text,
    "Montador por categorias": 'data-menu-option="1"' in public,
    "Fallback WhatsApp": 'id="whatsapp-fallback"' in public,
    "Painel de equipe": '@app.get("/admin/equipe")' in app_text,
    "Painel de cardápio": '@app.get("/admin/cardapio")' in app_text,
    "Painel de galeria": '@app.get("/admin/galeria")' in app_text,
    "Modo de categoria": "selection_mode" in app_text and "selection_mode" in admin_menu,
    "Limite por 100 convidados": "choices_per_100" in app_text and "choices_per_100" in admin_menu,
    "Categoria vinculada ao pacote": "package_feature" in app_text and "package_feature" in admin_menu,
    "Pacote controla entrada": "includes_entry" in app_text and "includes_entry" in content_template,
    "Pacote controla sobremesa": "includes_dessert" in app_text and "includes_dessert" in content_template,
    "PostgreSQL no Render": "fromDatabase:" in render_yaml and "buffet-marquinhos-db" in render_yaml,
    "Uploads em disco persistente": "mountPath: /var/data" in render_yaml and "UPLOAD_ROOT" in render_yaml,
    "Proteção contra SQLite efêmero": "PERSISTENCE_READY" in app_text and "Salvamento bloqueado por segurança" in app_text,
    "SECRET_KEY protege painel": "PRODUCTION_SECRET_READY" in app_text,
    "Seed não ressurge após exclusões": "bootstrap_version" in app_text and "first_bootstrap" in app_text,
    "API da agenda sem cache": 'response.headers["Cache-Control"] = "no-store"' in app_text,
    "Fuso do negócio configurado": "America/Sao_Paulo" in app_text and "BUSINESS_TIMEZONE" in render_yaml,
    "CSP de produção": "Content-Security-Policy" in app_text and "frame-ancestors 'none'" in app_text,
    "Proteção de upload por megapixels": "MAX_IMAGE_PIXELS" in app_text and "40 megapixels" in app_text,
    "Tratamento amigável de CSRF/400": "@app.errorhandler(400)" in app_text,
}
for label, ok in checks.items():
    require(ok, f"Verificação ausente: {label}")

# O clique em Enviar pelo WhatsApp não pode aguardar fetch/Promise antes de navegar.
submit_marker = "form?.addEventListener('submit',event=>{"
submit_start = main_js.find(submit_marker)
require(submit_start >= 0, "Handler de envio do orçamento ausente")
if submit_start >= 0:
    submit_block = main_js[submit_start:]
    require("await " not in submit_block, "O envio do WhatsApp contém await e pode ser bloqueado no iPhone")
    require("https://wa.me/" in submit_block, "Envio do orçamento não usa wa.me")
    require("window.location.href=whatsappUrl" in submit_block, "Navegação direta para WhatsApp ausente")

# A rota antiga de criação de item causava 404/405 e não pode reaparecer.
require('/admin/cardapio/itens/novo' not in app_text, "Rota antiga de novo item voltou ao app.py")
for template in ROOT.glob("templates/**/*.html"):
    require('/admin/cardapio/itens/novo' not in template.read_text(encoding="utf-8"), f"Template usa rota antiga de item: {template.name}")

# Não deve existir botão global de selecionar tudo, porque categorias têm regras diferentes.
require("select-menu-all" not in public, "Ainda existe botão de selecionar tudo no cardápio")

# Entrada/sobremesa devem depender de uma configuração explícita, não do nome da categoria.
require("data-requires-feature=\"{{ category.package_feature or 'always' }}\"" in public, "Template ainda depende do nome da categoria para entrada/sobremesa")
require("packageAwareMenuGroups" in main_js, "JavaScript não trata grupos vinculados ao pacote")

# Itens padrão solicitados pelo negócio devem nascer como informativos, e escolhas como escolha única.
for expected in [
    '"name": "Massas"',
    '"name": "Strogonoff"',
    '"name": "Lasanha"',
    '"name": "Churrasco"',
    '"name": "Saladas"',
    '"name": "Sobremesas"',
    '"name": "Incluso"',
]:
    require(expected in app_text, f"Estrutura padrão ausente: {expected}")

# Migrações não podem reescrever escolhas do administrador a cada restart.
version_guard = app_text.find("if version >= 3:")
version_two_guard = app_text.find("if version < 2:")
package_migration = app_text.find('package_flags = {', version_two_guard)
require(version_guard >= 0 and version_two_guard > version_guard and package_migration > version_two_guard, "Migração de pacotes pode sobrescrever escolhas após restart")
require("current.menu_structure_version = 3" in app_text, "Versão atual da migração do cardápio não foi registrada")

# Evita publicar credenciais reais por engano. Valores demonstrativos são permitidos.
for candidate in ROOT.rglob("*"):
    if candidate.resolve() == Path(__file__).resolve():
        continue
    if not candidate.is_file() or ".git" in candidate.parts or candidate.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".pyc"}:
        continue
    try:
        candidate_text = candidate.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        continue
    require("postgresql://usuario:senha@" not in candidate_text or candidate.name == ".env.example", f"Credencial Postgres suspeita em {candidate.name}")
    require(not re.search(r"(?i)ADMIN_PASSWORD\s*=\s*(?!troque-)[^\s#]{8,}", candidate_text), f"Senha administrativa possivelmente real em {candidate.name}")

# Documentação não pode orientar SQLite como banco de produção.
for doc_name in ["README.md", "MIGRACAO_RENDER_PRODUCAO.md", "PASSO_A_PASSO_PUBLICAR_E_USAR_ADMIN.md"]:
    doc = (ROOT / doc_name).read_text(encoding="utf-8")
    require("banco SQLite armazenado no disco" not in doc, f"Documentação antiga de SQLite em produção: {doc_name}")

# O painel desabilita o botão de POST no mesmo evento submit para reduzir duplo cadastro.
admin_js = (ROOT / "static" / "js" / "admin.js").read_text(encoding="utf-8")
require("submitter.disabled=true" in admin_js, "Proteção de duplo envio no painel ausente")
require("window.setTimeout" not in admin_js[admin_js.find("form[method="):], "Proteção de duplo envio está atrasada por setTimeout")

# Node, quando disponível, faz validação real da sintaxe JavaScript.
node = shutil.which("node")
if node:
    for js_file in [ROOT / "static" / "js" / "main.js", ROOT / "static" / "js" / "admin.js"]:
        result = subprocess.run([node, "--check", str(js_file)], capture_output=True, text=True)
        if result.returncode != 0:
            errors.append(f"JavaScript inválido em {js_file.name}: {result.stderr.strip()}")

if errors:
    raise SystemExit("\n".join(errors))
print("Auditoria estática aprovada.")
