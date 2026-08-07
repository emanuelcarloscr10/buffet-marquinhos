from __future__ import annotations
import ast
import re
from pathlib import Path
from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[1]
errors = []

compile((ROOT / "app.py").read_text(encoding="utf-8"), "app.py", "exec")
env = Environment()
for template in ROOT.glob("templates/**/*.html"):
    env.parse(template.read_text(encoding="utf-8"))

app_text = (ROOT / "app.py").read_text(encoding="utf-8")
tree = ast.parse(app_text)
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

for filename in re.findall(r'["\']images/([^"\']+\.(?:png|jpe?g|webp))["\']', app_text):
    if not (ROOT / "static" / "images" / filename).exists():
        errors.append(f"Imagem ausente: images/{filename}")

public = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
ids = set(re.findall(r'\bid=["\']([^"\']+)', public))
for target in re.findall(r'href=["\']#([^"\']+)', public):
    if target and target not in ids:
        errors.append(f"Âncora sem destino: #{target}")

checks = {
    "WhatsApp": "5548988608441",
    "Rota health": '@app.get("/health")',
    "Montador": 'name="cardapio"',
    "Fallback WhatsApp": 'id="whatsapp-fallback"',
    "Painel de equipe": '@app.get("/admin/equipe")',
    "Painel de cardápio": '@app.get("/admin/cardapio")',
    "Painel de galeria": '@app.get("/admin/galeria")',
    "Orientação por categoria": 'selection_help',
    "Mínimo por categoria": 'min_choices',
    "Máximo por categoria": 'max_choices',
}
for label, value in checks.items():
    if value not in app_text and value not in public:
        errors.append(f"Verificação ausente: {label}")

if errors:
    raise SystemExit("\n".join(errors))
print("Auditoria estática aprovada.")
