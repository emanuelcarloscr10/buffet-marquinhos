from __future__ import annotations

import calendar
import os
import re
import secrets
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from functools import wraps
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from flask import (
    Flask,
    abort,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_from_directory,
    session,
    url_for,
)
from flask_sqlalchemy import SQLAlchemy
from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy import UniqueConstraint, inspect, text
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.utils import secure_filename

BASE_DIR = Path(__file__).resolve().parent
INSTANCE_DIR = BASE_DIR / "instance"
DEFAULT_DB = "sqlite:///" + str(INSTANCE_DIR / "buffet.db")
RUNNING_ON_RENDER = os.getenv("RENDER") == "true"
SECRET_KEY_VALUE = os.getenv("SECRET_KEY", "").strip()
DATABASE_URL = os.getenv("DATABASE_URL", DEFAULT_DB).strip()

# O Render fornece URLs no formato postgresql://. Explicitamos o driver psycopg 3
# para não depender de um driver implícito e manter conexões mais previsíveis.
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg://", 1)
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)

# Em produção, o site público pode continuar online enquanto o PostgreSQL é
# configurado. Porém o painel bloqueia qualquer gravação enquanto o banco ainda
# estiver em SQLite, evitando que o administrador cadastre dados que desaparecerão
# no próximo deploy/restart.
PRODUCTION_SECRET_READY = (not RUNNING_ON_RENDER) or bool(SECRET_KEY_VALUE)
PERSISTENCE_READY = (not RUNNING_ON_RENDER) or DATABASE_URL.startswith("postgresql+")

UPLOAD_ROOT = Path(os.getenv("UPLOAD_ROOT", str(BASE_DIR / "static" / "uploads"))).resolve()
MAX_UPLOAD_MB = 12
ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
MAX_IMAGE_PIXELS = 40_000_000

try:
    BUSINESS_TZ = ZoneInfo(os.getenv("BUSINESS_TIMEZONE", "America/Sao_Paulo"))
except ZoneInfoNotFoundError:
    # Fallback seguro caso a imagem do sistema não traga a base IANA de fusos.
    BUSINESS_TZ = timezone(timedelta(hours=-3))

app = Flask(__name__)
app.config.update(
    SECRET_KEY=SECRET_KEY_VALUE or "desenvolvimento-troque-esta-chave",
    SQLALCHEMY_DATABASE_URI=DATABASE_URL,
    SQLALCHEMY_TRACK_MODIFICATIONS=False,
    SQLALCHEMY_ENGINE_OPTIONS={"pool_pre_ping": True, "pool_recycle": 300}
    if DATABASE_URL.startswith("postgresql+")
    else {},
    MAX_CONTENT_LENGTH=MAX_UPLOAD_MB * 1024 * 1024,
    PERMANENT_SESSION_LIFETIME=60 * 60 * 12,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=RUNNING_ON_RENDER or os.getenv("HTTPS_ONLY") == "1",
)
db = SQLAlchemy(app)

ACTIVE_STATUSES = {"reservado", "confirmado"}
STATUS_LABELS = {
    "reservado": "Reservado",
    "confirmado": "Confirmado",
    "cancelado": "Cancelado",
}
GALLERY_CATEGORIES = {
    "churrasco": "Churrasco",
    "pratos": "Pratos",
    "saladas": "Saladas",
    "sobremesas": "Sobremesas",
}
MENU_SELECTION_MODES = {
    "info": "Somente informativa (sem seleção)",
    "single": "Escolha única (1 opção)",
    "multiple": "Múltipla escolha",
}
MENU_PACKAGE_FEATURES = {
    "always": "Sempre mostrar",
    "entry": "Somente em pacotes com entrada",
    "dessert": "Somente em pacotes com sobremesa",
}


class Setting(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    max_events_per_day = db.Column(db.Integer, nullable=False, default=2)
    # Garante que os dados de demonstração/padrão sejam inseridos apenas na primeira
    # inicialização do banco. Exclusões feitas depois pelo administrador são respeitadas.
    bootstrap_version = db.Column(db.Integer, nullable=False, default=0)
    # Controla migrações de estrutura do cardápio que precisam ocorrer apenas uma vez.
    menu_structure_version = db.Column(db.Integer, nullable=False, default=0)


class SiteContent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    brand_name = db.Column(db.String(120), nullable=False, default="Buffet do Marquinhos")
    page_title = db.Column(db.String(180), nullable=False)
    meta_description = db.Column(db.String(320), nullable=False)

    hero_badge = db.Column(db.String(180), nullable=False)
    hero_title = db.Column(db.String(220), nullable=False)
    hero_highlight = db.Column(db.String(100), nullable=False)
    hero_description = db.Column(db.Text, nullable=False)

    story_eyebrow = db.Column(db.String(100), nullable=False)
    story_title = db.Column(db.String(220), nullable=False)
    story_highlight = db.Column(db.String(100), nullable=False)
    story_text = db.Column(db.Text, nullable=False)

    pricing_eyebrow = db.Column(db.String(100), nullable=False)
    pricing_title = db.Column(db.String(220), nullable=False)
    pricing_description = db.Column(db.Text, nullable=False)
    pricing_notice = db.Column(db.Text, nullable=False)
    dessert_notice = db.Column(
        db.Text,
        nullable=False,
        default="São disponibilizadas 3 opções de sobremesas a cada 100 convidados.",
    )
    travel_notice = db.Column(db.Text, nullable=False)

    menu_eyebrow = db.Column(db.String(100), nullable=False)
    menu_title = db.Column(db.String(220), nullable=False)
    menu_description = db.Column(db.Text, nullable=False)

    availability_eyebrow = db.Column(db.String(100), nullable=False)
    availability_title = db.Column(db.String(220), nullable=False)
    availability_description = db.Column(db.Text, nullable=False)

    gallery_eyebrow = db.Column(db.String(100), nullable=False)
    gallery_title = db.Column(db.String(220), nullable=False)

    contact_eyebrow = db.Column(db.String(100), nullable=False)
    contact_title = db.Column(db.String(220), nullable=False)
    contact_description = db.Column(db.Text, nullable=False)

    since_year = db.Column(db.Integer, nullable=False, default=2013)
    base_city = db.Column(db.String(120), nullable=False, default="Praia Grande")
    whatsapp_number = db.Column(db.String(30), nullable=False, default="5548988608441")
    whatsapp_display = db.Column(db.String(30), nullable=False, default="(48) 98860-8441")
    instagram_handle = db.Column(db.String(120), nullable=False, default="buffeteventos_marquinhos")
    address = db.Column(db.String(260), nullable=False)
    cnpj = db.Column(db.String(40), nullable=False)
    footer_tagline = db.Column(db.String(180), nullable=False)

    logo_storage = db.Column(db.String(20), nullable=False, default="static")
    logo_filename = db.Column(db.String(260), nullable=False, default="images/logo-marquinhos.png")
    official_menu_storage = db.Column(db.String(20), nullable=False, default="static")
    official_menu_filename = db.Column(db.String(260), nullable=False, default="images/cardapio-oficial.webp")
    hero_image_id = db.Column(db.Integer, nullable=True)
    about_image_1_id = db.Column(db.Integer, nullable=True)
    about_image_2_id = db.Column(db.Integer, nullable=True)
    about_image_3_id = db.Column(db.Integer, nullable=True)


class CorporateSection(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    eyebrow = db.Column(db.String(100), nullable=False, default="Quem somos")
    title = db.Column(db.String(220), nullable=False, default="Pessoas que fazem")
    highlight = db.Column(db.String(120), nullable=False, default="tudo acontecer.")
    description = db.Column(db.Text, nullable=False, default=(
        "Por trás de cada evento existe uma equipe dedicada ao preparo, à organização "
        "e ao atendimento. Conheça as pessoas que fazem parte da história do Buffet do "
        "Marquinhos e trabalham para que cada celebração seja conduzida com cuidado."
    ))


class PricingPackage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(140), nullable=False)
    price = db.Column(db.Numeric(10, 2), nullable=False)
    description = db.Column(db.Text, nullable=False, default="")
    badge = db.Column(db.String(60), nullable=True)
    includes_entry = db.Column(db.Boolean, nullable=False, default=False)
    includes_dessert = db.Column(db.Boolean, nullable=False, default=False)
    featured = db.Column(db.Boolean, nullable=False, default=False)
    active = db.Column(db.Boolean, nullable=False, default=True)
    sort_order = db.Column(db.Integer, nullable=False, default=0)


class MenuCategory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.String(240), nullable=True)
    # info = apenas mostra os itens; single = rádio com uma escolha;
    # multiple = checkboxes com limite configurável.
    selection_mode = db.Column(db.String(20), nullable=False, default="info")
    selection_help = db.Column(db.String(240), nullable=True)
    # Permite vincular a categoria explicitamente ao pacote sem depender do nome.
    package_feature = db.Column(db.String(20), nullable=False, default="always")
    min_choices = db.Column(db.Integer, nullable=False, default=0)
    max_choices = db.Column(db.Integer, nullable=False, default=0)
    # Ex.: sobremesas = 3 opções a cada 100 convidados. Zero desativa a regra.
    choices_per_100 = db.Column(db.Integer, nullable=False, default=0)
    active = db.Column(db.Boolean, nullable=False, default=True)
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    items = db.relationship(
        "MenuItem",
        backref="category",
        cascade="all, delete-orphan",
        order_by="MenuItem.sort_order, MenuItem.id",
    )


class MenuItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    category_id = db.Column(db.Integer, db.ForeignKey("menu_category.id"), nullable=False, index=True)
    name = db.Column(db.String(240), nullable=False)
    active = db.Column(db.Boolean, nullable=False, default=True)
    sort_order = db.Column(db.Integer, nullable=False, default=0)


class GalleryImage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    storage = db.Column(db.String(20), nullable=False, default="static")
    filename = db.Column(db.String(260), nullable=False)
    category = db.Column(db.String(40), nullable=False, default="pratos")
    active = db.Column(db.Boolean, nullable=False, default=True)
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class TeamMember(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(140), nullable=False)
    role = db.Column(db.String(160), nullable=False, default="")
    bio = db.Column(db.Text, nullable=False, default="")
    image_storage = db.Column(db.String(20), nullable=False, default="static")
    image_filename = db.Column(db.String(260), nullable=False, default="images/equipe-placeholder.webp")
    active = db.Column(db.Boolean, nullable=False, default=True)
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class Event(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    event_date = db.Column(db.Date, nullable=False, index=True)
    event_time = db.Column(db.Time, nullable=True)
    client_name = db.Column(db.String(140), nullable=False)
    phone = db.Column(db.String(40), nullable=True)
    city = db.Column(db.String(120), nullable=False, default="Praia Grande")
    venue = db.Column(db.String(180), nullable=True)
    guests = db.Column(db.Integer, nullable=True)
    event_type = db.Column(db.String(80), nullable=True)
    menu = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), nullable=False, default="reservado")
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    @property
    def counts_toward_capacity(self) -> bool:
        return self.status in ACTIVE_STATUSES


class BlockedDate(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    blocked_date = db.Column(db.Date, nullable=False, unique=True, index=True)
    reason = db.Column(db.String(220), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    __table_args__ = (UniqueConstraint("blocked_date", name="uq_blocked_date"),)


def default_site_content() -> SiteContent:
    return SiteContent(
        page_title="Buffet do Marquinhos | Eventos em Praia Grande - SC",
        meta_description=(
            "Desde 2013 no ramo de buffet de eventos, atendendo casamentos, aniversários, "
            "formaturas e eventos corporativos em Praia Grande e região."
        ),
        hero_badge="Desde 2013 no ramo de buffet de eventos",
        hero_title="Sabores que fazem parte da sua",
        hero_highlight="história.",
        hero_description=(
            "Churrasco, pratos completos, saladas e sobremesas preparados com carinho "
            "para casamentos, aniversários, formaturas, eventos corporativos e celebrações especiais."
        ),
        story_eyebrow="Nossa história",
        story_title="Tradição e dedicação",
        story_highlight="desde 2013.",
        story_text=(
            "Desde 2013, o Buffet do Marquinhos atua no ramo de buffet de eventos, levando "
            "sabor, cuidado e dedicação para casamentos, aniversários, formaturas, eventos "
            "corporativos e outras comemorações. Cada cardápio é montado conforme as escolhas do cliente, com "
            "atenção à preparação, à apresentação e ao serviço."
        ),
        pricing_eyebrow="Valores por pessoa",
        pricing_title="Escolha o pacote ideal.",
        pricing_description="Valores conforme o cardápio oficial do Buffet do Marquinhos.",
        pricing_notice=(
            "Para eventos abaixo de 100 convidados, acrescenta-se R$ 7,00 por pessoa. "
            "Crianças de 5 a 10 anos pagam metade."
        ),
        dessert_notice="São disponibilizadas 3 opções de sobremesas a cada 100 convidados.",
        travel_notice=(
            "Eventos realizados fora de Praia Grande poderão ter acréscimo de deslocamento, "
            "calculado conforme a cidade e o local do evento."
        ),
        menu_eyebrow="Cardápio do buffet",
        menu_title="Escolha apenas o que varia no seu evento.",
        menu_description=(
            "Churrasco, saladas e os itens inclusos seguem o padrão do buffet. "
            "Nas categorias indicadas, você escolhe apenas a opção desejada, como massa, "
            "strogonoff, lasanha e sobremesas. Pedidos especiais continuam sujeitos a consulta."
        ),
        availability_eyebrow="Agenda do buffet",
        availability_title="Consulte a disponibilidade.",
        availability_description=(
            "Escolha a data do evento. O sistema mostra automaticamente se ainda temos vagas, "
            "se resta apenas uma vaga ou se a agenda já está lotada."
        ),
        gallery_eyebrow="Fotos reais",
        gallery_title="Um pouco do nosso buffet.",
        contact_eyebrow="Solicite seu orçamento",
        contact_title="Vamos preparar seu evento?",
        contact_description=(
            "Preencha as informações. Ao enviar, o pedido será aberto no WhatsApp com a mensagem pronta."
        ),
        address="Rua Antônio Rampinelli, 466, Alvorada, Praia Grande–SC",
        cnpj="49.792.951/0001-30",
        footer_tagline="Você vai amar o sabor.",
    )


def seed_content() -> None:
    current_settings = Setting.query.first()
    if not current_settings:
        current_settings = Setting(max_events_per_day=2, bootstrap_version=0, menu_structure_version=0)
        db.session.add(current_settings)
        db.session.flush()

    first_bootstrap = (current_settings.bootstrap_version or 0) < 1

    site = SiteContent.query.first()
    if not site:
        site = default_site_content()
        db.session.add(site)
        db.session.flush()

    legacy_menu_descriptions = {
        "As opções podem ser combinadas conforme o perfil e o tamanho do evento.",
        "As opções podem ser combinadas conforme o perfil e o tamanho do evento. Além do cardápio apresentado, também elaboramos cardápios personalizados de acordo com o gosto do cliente, com possibilidade de incluir pratos que não estejam no cardápio padrão, mediante consulta e orçamento.",
    }
    if first_bootstrap and site.menu_description in legacy_menu_descriptions:
        site.menu_eyebrow = "Cardápio do buffet"
        site.menu_title = "Escolha apenas o que varia no seu evento."
        site.menu_description = (
            "Churrasco, saladas e os itens inclusos seguem o padrão do buffet. "
            "Nas categorias indicadas, você escolhe apenas a opção desejada, como massa, "
            "strogonoff, lasanha e sobremesas. Pedidos especiais continuam sujeitos a consulta."
        )

    team_section = CorporateSection.query.first()
    if not team_section:
        team_section = CorporateSection(
            eyebrow="Quem somos",
            title="Pessoas que fazem",
            highlight="tudo acontecer.",
            description=(
                "Por trás de cada evento existe uma equipe dedicada ao preparo, à organização "
                "e ao atendimento. Conheça as pessoas que fazem parte da história do Buffet do "
                "Marquinhos e trabalham para que cada celebração seja conduzida com cuidado."
            ),
        )
        db.session.add(team_section)
    elif first_bootstrap and team_section.eyebrow == "Clientes e eventos":
        team_section.eyebrow = "Quem somos"
        team_section.title = "Pessoas que fazem"
        team_section.highlight = "tudo acontecer."
        team_section.description = (
            "Por trás de cada evento existe uma equipe dedicada ao preparo, à organização "
            "e ao atendimento. Conheça as pessoas que fazem parte da história do Buffet do "
            "Marquinhos e trabalham para que cada celebração seja conduzida com cuidado."
        )

    if first_bootstrap and PricingPackage.query.count() == 0:
        packages = [
            PricingPackage(
                name="Entrada + sobremesa",
                price=Decimal("80.00"),
                description="Inclui entrada, pratos principais, churrasco, saladas e sobremesas.",
                badge="Completo",
                includes_entry=True,
                includes_dessert=True,
                featured=True,
                sort_order=1,
            ),
            PricingPackage(
                name="Com entrada",
                price=Decimal("74.00"),
                description="Entrada, pratos principais, churrasco e saladas.",
                includes_entry=True,
                includes_dessert=False,
                sort_order=2,
            ),
            PricingPackage(
                name="Com sobremesa",
                price=Decimal("73.00"),
                description="Pratos principais, churrasco, saladas e sobremesas.",
                includes_entry=False,
                includes_dessert=True,
                sort_order=3,
            ),
            PricingPackage(
                name="Buffet essencial",
                price=Decimal("67.00"),
                description="Sem entrada e sem sobremesa.",
                includes_entry=False,
                includes_dessert=False,
                sort_order=4,
            ),
        ]
        db.session.add_all(packages)

    if first_bootstrap and MenuCategory.query.count() == 0:
        menu_seed = [
            {
                "name": "Entradas",
                "description": "As opções de entrada são oferecidas conforme o pacote escolhido.",
                "mode": "info",
                "feature": "entry",
                "items": ["Risoto de alho-poró", "Escondidinho de carne-seca com aipim"],
            },
            {
                "name": "Acompanhamentos",
                "description": "Itens do cardápio servidos conforme a composição do buffet.",
                "mode": "info",
                "items": [
                    "Arroz branco",
                    "Arroz vegetariano, à grega ou campeiro",
                    "Aipim com bacon e queijo",
                ],
            },
            {
                "name": "Massas",
                "mode": "single",
                "help": "Escolha 1 opção de massa.",
                "min": 1,
                "max": 1,
                "items": ["Alho e óleo", "Carbonara", "Molho sugo"],
            },
            {
                "name": "Strogonoff",
                "mode": "single",
                "help": "Escolha carne ou frango.",
                "min": 1,
                "max": 1,
                "items": ["Carne", "Frango"],
            },
            {
                "name": "Lasanha",
                "mode": "single",
                "help": "Escolha 1 sabor.",
                "min": 1,
                "max": 1,
                "items": ["Frango", "Bolonhesa", "Vegetariana", "Quatro queijos"],
            },
            {
                "name": "Churrasco",
                "description": "Seleção padrão do buffet: as variedades abaixo fazem parte do serviço e não precisam ser escolhidas.",
                "mode": "info",
                "items": ["Entrecot, vazio e maminha", "Costelinha suína", "Sobrecoxa de frango", "Salsichão colonial", "Abacaxi com canela"],
            },
            {
                "name": "Saladas",
                "description": "Servimos oito variedades, incluindo folhas, legumes e vinagrete.",
                "mode": "info",
                "items": ["Oito variedades de saladas", "Folhas, legumes e vinagrete"],
            },
            {
                "name": "Sobremesas",
                "description": "Disponíveis nos pacotes que incluem sobremesa.",
                "mode": "multiple",
                "feature": "dessert",
                "help": "Escolha até 3 opções a cada 100 convidados.",
                "min": 0,
                "max": 0,
                "per100": 3,
                "items": ["Mousses: maracujá, uva e Ninho", "Bombom de travessa", "Doce sensação", "Manjar de ameixa", "Abacaxi com creme branco", "Pavê de Sonho de Valsa", "Torta de bolacha"],
            },
            {
                "name": "Incluso",
                "description": "Itens incluídos no serviço; não é necessário selecionar.",
                "mode": "info",
                "items": ["Taças", "Pratos", "Talheres em inox", "Guardanapos de papel"],
            },
        ]
        for category_order, data in enumerate(menu_seed, start=1):
            category = MenuCategory(
                name=data["name"],
                description=data.get("description"),
                selection_mode=data.get("mode", "info"),
                selection_help=data.get("help"),
                package_feature=data.get("feature", "always"),
                min_choices=data.get("min", 0),
                max_choices=data.get("max", 0),
                choices_per_100=data.get("per100", 0),
                sort_order=category_order * 10,
            )
            db.session.add(category)
            db.session.flush()
            for item_order, item_name in enumerate(data["items"], start=1):
                db.session.add(MenuItem(category_id=category.id, name=item_name, sort_order=item_order))
        current_settings.menu_structure_version = 3

    if first_bootstrap and GalleryImage.query.count() == 0:
        gallery_seed = [
            # 1. Churrasco
            ("images/churrasco-carne-nova.webp", "churrasco"),
            ("images/fogo-carne-2.webp", "churrasco"),
            ("images/frango-assado.webp", "churrasco"),
            ("images/carne-suina.webp", "churrasco"),
            ("images/fogo-carne-3.webp", "churrasco"),
            ("images/salsichao.webp", "churrasco"),

            # 2. Pratos — fotografias atualizadas
            ("images/prato-novo-arroz-colorido.webp", "pratos"),
            ("images/prato-novo-cremoso.webp", "pratos"),
            ("images/prato-novo-arroz-carne.webp", "pratos"),
            ("images/prato-novo-gratinado.webp", "pratos"),
            ("images/prato-novo-aipim-bacon.webp", "pratos"),
            ("images/prato-novo-mesa-posta.webp", "pratos"),

            # 3. Saladas
            ("images/salada-verde.webp", "saladas"),
            ("images/salada-cremosa.webp", "saladas"),
            ("images/salada-beterraba.webp", "saladas"),
            ("images/salada-frutas.webp", "saladas"),
            ("images/cenoura-tomate.webp", "saladas"),
            ("images/salada-tomate.webp", "saladas"),
            ("images/maionese.webp", "saladas"),

            # 4. Sobremesas
            ("images/mousse-limao.webp", "sobremesas"),
            ("images/sobremesa-chocolate-morango.webp", "sobremesas"),
            ("images/sobremesa-chocolate-granulado.webp", "sobremesas"),
            ("images/sobremesa-bombom.webp", "sobremesas"),
            ("images/sobremesa-uva.webp", "sobremesas"),
            ("images/sobremesa-maracuja.webp", "sobremesas"),
        ]
        seeded_images = []
        for order, (filename, category) in enumerate(gallery_seed, start=1):
            image = GalleryImage(storage="static", filename=filename, category=category, sort_order=order)
            db.session.add(image)
            seeded_images.append(image)
        db.session.flush()
        site.hero_image_id = seeded_images[1].id

        # A primeira foto da galeria de churrasco foi substituída, mas a imagem
        # antiga continua na seção "Nossa história", sem aparecer na galeria.
        original_about_image = GalleryImage(
            storage="static",
            filename="images/fogo-carne-1.webp",
            category="churrasco",
            active=False,
            sort_order=9999,
        )
        db.session.add(original_about_image)
        db.session.flush()

        site.about_image_1_id = original_about_image.id
        site.about_image_2_id = seeded_images[12].id
        site.about_image_3_id = seeded_images[24].id


    # Atualiza automaticamente as seis fotografias padrão da categoria Pratos
    # em instalações que já possuem banco de dados. A troca é feita apenas
    # quando o arquivo antigo padrão ainda está cadastrado, preservando fotos
    # personalizadas enviadas posteriormente pelo painel.
    prato_photo_updates = {
        "images/massa-cremosa.webp": "images/prato-novo-arroz-colorido.webp",
        "images/aipim-bacon.webp": "images/prato-novo-cremoso.webp",
        "images/strogonoff-novo.webp": "images/prato-novo-arroz-carne.webp",
        "images/arroz-colorido.webp": "images/prato-novo-gratinado.webp",
        "images/mesa-buffet.webp": "images/prato-novo-aipim-bacon.webp",
        "images/gratinado-2.webp": "images/prato-novo-mesa-posta.webp",
    }
    for old_filename, new_filename in prato_photo_updates.items():
        if not first_bootstrap:
            break
        legacy_photo = GalleryImage.query.filter_by(
            storage="static",
            filename=old_filename,
            category="pratos",
        ).first()
        if legacy_photo:
            legacy_photo.filename = new_filename

    if first_bootstrap:
        for legacy_image in GalleryImage.query.filter_by(category="clientes").all():
            db.session.delete(legacy_image)

    if first_bootstrap and TeamMember.query.count() == 0:
        db.session.add_all([
            TeamMember(
                name="Marquinhos",
                role="Proprietário e fundador",
                bio="À frente do buffet, acompanha a preparação, a organização e a realização de cada evento.",
                image_storage="static",
                image_filename="images/equipe-marquinhos.webp",
                active=True,
                sort_order=1,
            ),
            TeamMember(
                name="Virgínia",
                role="Proprietária, fundadora e responsável pela cozinha",
                bio=(
                    "Participa da preparação e da organização dos eventos, coordenando a cozinha "
                    "e sendo responsável pela elaboração dos alimentos do buffet, para que cada "
                    "serviço seja conduzido com cuidado, qualidade e dedicação."
                ),
                image_storage="static",
                image_filename="images/equipe-virginia.webp",
                active=True,
                sort_order=2,
            ),
            TeamMember(
                name="Equipe do Buffet do Marquinhos",
                role="Preparo, organização e atendimento dos eventos",
                bio=(
                    "Uma equipe comprometida com a cozinha, o churrasco, a montagem e o atendimento, "
                    "trabalhando em conjunto para oferecer uma experiência acolhedora aos convidados."
                ),
                image_storage="static",
                image_filename="images/equipe-grupo.webp",
                active=True,
                sort_order=3,
            ),
        ])

    if first_bootstrap:
        current_settings.bootstrap_version = 1

    db.session.commit()


def ensure_schema_updates() -> None:
    """Aplica apenas migrações aditivas, seguras para SQLite e PostgreSQL."""
    inspector = inspect(db.engine)
    tables = set(inspector.get_table_names())

    statements: list[str] = []

    if "site_content" in tables:
        columns = {column["name"] for column in inspector.get_columns("site_content")}
        if "dessert_notice" not in columns:
            statements.append("ALTER TABLE site_content ADD COLUMN dessert_notice TEXT")

    if "setting" in tables:
        columns = {column["name"] for column in inspector.get_columns("setting")}
        if "bootstrap_version" not in columns:
            statements.append(
                "ALTER TABLE setting ADD COLUMN bootstrap_version INTEGER NOT NULL DEFAULT 0"
            )
        if "menu_structure_version" not in columns:
            statements.append(
                "ALTER TABLE setting ADD COLUMN menu_structure_version INTEGER NOT NULL DEFAULT 0"
            )

    if "pricing_package" in tables:
        columns = {column["name"] for column in inspector.get_columns("pricing_package")}
        if "includes_entry" not in columns:
            statements.append(
                "ALTER TABLE pricing_package ADD COLUMN includes_entry BOOLEAN NOT NULL DEFAULT FALSE"
            )
        if "includes_dessert" not in columns:
            statements.append(
                "ALTER TABLE pricing_package ADD COLUMN includes_dessert BOOLEAN NOT NULL DEFAULT FALSE"
            )

    if "menu_category" in tables:
        columns = {column["name"] for column in inspector.get_columns("menu_category")}
        if "selection_mode" not in columns:
            statements.append(
                "ALTER TABLE menu_category ADD COLUMN selection_mode VARCHAR(20) NOT NULL DEFAULT 'info'"
            )
        if "selection_help" not in columns:
            statements.append("ALTER TABLE menu_category ADD COLUMN selection_help VARCHAR(240)")
        if "package_feature" not in columns:
            statements.append(
                "ALTER TABLE menu_category ADD COLUMN package_feature VARCHAR(20) NOT NULL DEFAULT 'always'"
            )
        if "min_choices" not in columns:
            statements.append(
                "ALTER TABLE menu_category ADD COLUMN min_choices INTEGER NOT NULL DEFAULT 0"
            )
        if "max_choices" not in columns:
            statements.append(
                "ALTER TABLE menu_category ADD COLUMN max_choices INTEGER NOT NULL DEFAULT 0"
            )
        if "choices_per_100" not in columns:
            statements.append(
                "ALTER TABLE menu_category ADD COLUMN choices_per_100 INTEGER NOT NULL DEFAULT 0"
            )

    if statements:
        with db.engine.begin() as connection:
            for statement in statements:
                connection.execute(text(statement))

    # Preenche o texto antigo somente quando a coluna acabou de ser criada ou está vazia.
    if "site_content" in tables:
        with db.engine.begin() as connection:
            connection.execute(
                text(
                    "UPDATE site_content SET dessert_notice = :notice "
                    "WHERE dessert_notice IS NULL OR dessert_notice = ''"
                ),
                {"notice": "São disponibilizadas 3 opções de sobremesas a cada 100 convidados."},
            )


def _find_or_create_category(name: str, sort_order: int) -> MenuCategory:
    category = MenuCategory.query.filter(db.func.lower(MenuCategory.name) == name.lower()).first()
    if category:
        return category
    category = MenuCategory(name=name, sort_order=sort_order, active=True)
    db.session.add(category)
    db.session.flush()
    return category


def _add_item_if_missing(category: MenuCategory, name: str, sort_order: int) -> None:
    exists = MenuItem.query.filter(
        MenuItem.category_id == category.id,
        db.func.lower(MenuItem.name) == name.lower(),
    ).first()
    if not exists:
        db.session.add(
            MenuItem(category_id=category.id, name=name, active=True, sort_order=sort_order)
        )


def recommended_menu_structure() -> list[dict[str, object]]:
    return [
        {
            "name": "Entradas",
            "description": "Disponíveis nos pacotes com entrada.",
            "mode": "single",
            "feature": "entry",
            "help": "Escolha 1 entrada.",
            "min": 1,
            "max": 1,
            "items": [
                "Risoto de alho poró",
                "Escondidinho de carne seca com aipim",
            ],
        },
        {
            "name": "Arroz branco",
            "description": "Já faz parte de todos os eventos; não precisa selecionar.",
            "mode": "info",
            "items": ["Arroz branco"],
        },
        {
            "name": "Arroz especial",
            "description": "Além do arroz branco, escolha 1 opção especial.",
            "mode": "single",
            "help": "Escolha 1 opção.",
            "min": 1,
            "max": 1,
            "items": ["Arroz à grega", "Arroz campeiro", "Arroz vegetariano"],
        },
        {
            "name": "Acompanhamento especial",
            "description": "Escolha entre aipim com bacon e queijo ou uma das opções de massa.",
            "mode": "single",
            "help": "Escolha 1 opção.",
            "min": 1,
            "max": 1,
            "items": [
                "Aipim com bacon e queijo",
                "Massa alho e óleo",
                "Massa carbonara",
                "Massa ao molho sugo",
            ],
        },
        {
            "name": "Strogonoff",
            "description": "Escolha o sabor do strogonoff.",
            "mode": "single",
            "help": "Escolha 1 sabor.",
            "min": 1,
            "max": 1,
            "items": ["Carne", "Frango"],
        },
        {
            "name": "Lasanha",
            "description": "Escolha o sabor da lasanha.",
            "mode": "single",
            "help": "Escolha 1 sabor.",
            "min": 1,
            "max": 1,
            "items": ["Frango", "Bolonhesa", "Vegetariana", "Quatro queijos"],
        },
        {
            "name": "Churrasco",
            "description": "Seleção padrão do buffet: as variedades abaixo fazem parte do serviço e não precisam ser escolhidas.",
            "mode": "info",
            "items": [
                "Carne de gado (entrecot, vazio e maminha)",
                "Carne suína (costelinha)",
                "Frango (sobrecoxa)",
                "Salsichão tipo colonial",
                "Abacaxi com canela",
            ],
        },
        {
            "name": "Saladas",
            "description": "Servimos 8 variedades: folhas, legumes e vinagrete.",
            "mode": "info",
            "items": ["8 variedades de saladas", "Folhas", "Legumes", "Vinagrete"],
        },
        {
            "name": "Sobremesas",
            "description": "Disponíveis nos pacotes com sobremesa.",
            "mode": "multiple",
            "feature": "dessert",
            "help": "Escolha até 3 opções a cada 100 convidados.",
            "min": 0,
            "max": 0,
            "per100": 3,
            "items": [
                "Mousse de maracujá",
                "Mousse de uva",
                "Mousse de Ninho",
                "Bombom de travessa",
                "Doce sensação",
                "Manjar de ameixa",
                "Abacaxi com creme branco",
                "Pavê de Sonho de Valsa",
                "Torta de bolacha",
            ],
        },
        {
            "name": "Incluso",
            "description": "Itens incluídos no serviço; não é necessário selecionar.",
            "mode": "info",
            "items": ["Taças", "Pratos", "Talheres em inox", "Guardanapos de papel"],
        },
    ]


def apply_recommended_menu_structure() -> None:
    for category in MenuCategory.query.order_by(MenuCategory.sort_order, MenuCategory.id).all():
        db.session.delete(category)
    db.session.flush()

    for category_order, data in enumerate(recommended_menu_structure(), start=1):
        category = MenuCategory(
            name=str(data["name"]),
            description=data.get("description"),
            selection_mode=str(data.get("mode", "info")),
            selection_help=data.get("help"),
            package_feature=str(data.get("feature", "always")),
            min_choices=int(data.get("min", 0) or 0),
            max_choices=int(data.get("max", 0) or 0),
            choices_per_100=int(data.get("per100", 0) or 0),
            active=True,
            sort_order=category_order * 10,
        )
        db.session.add(category)
        db.session.flush()
        for item_order, item_name in enumerate(data.get("items", []), start=1):
            db.session.add(
                MenuItem(
                    category_id=category.id,
                    name=str(item_name),
                    active=True,
                    sort_order=item_order,
                )
            )

    site = SiteContent.query.first()
    if site:
        site.menu_eyebrow = "Cardápio do buffet"
        site.menu_title = "Escolha apenas o que realmente varia no seu evento."
        site.menu_description = (
            "O cliente seleciona somente as opções que mudam no cardápio, como entrada, arroz especial, "
            "acompanhamento, strogonoff, lasanha e sobremesas. Churrasco, saladas, arroz branco e os itens "
            "inclusos já seguem o padrão do buffet."
        )


def apply_data_migrations() -> None:
    """Converte com cuidado bancos antigos para a estrutura atual do cardápio.

    Cada versão é aplicada uma única vez. Isso evita que um restart/deploy volte a
    impor os padrões sobre escolhas que o administrador alterou depois.
    """
    current = Setting.query.first()
    if not current:
        current = Setting(max_events_per_day=2, bootstrap_version=0, menu_structure_version=0)
        db.session.add(current)
        db.session.flush()

    version = current.menu_structure_version or 0
    if version >= 4:
        db.session.commit()
        return

    if version < 2:
        # Flags dos quatro pacotes padrão são preenchidas apenas na migração do
        # formato antigo. Depois disso, o painel é a fonte de verdade.
        package_flags = {
            "entrada + sobremesa": (True, True),
            "com entrada": (True, False),
            "com sobremesa": (False, True),
            "buffet essencial": (False, False),
        }
        for package in PricingPackage.query.all():
            flags = package_flags.get(package.name.strip().lower())
            if flags:
                package.includes_entry, package.includes_dessert = flags

        # Categorias antigas que já tinham limite configurado continuam selecionáveis.
        for category in MenuCategory.query.all():
            if category.max_choices == 1:
                category.selection_mode = "single"
            elif category.max_choices > 1 or category.min_choices > 0:
                category.selection_mode = "multiple"
            else:
                category.selection_mode = "info"
            category.choices_per_100 = max(0, category.choices_per_100 or 0)

        by_name = {
            category.name.strip().lower(): category for category in MenuCategory.query.all()
        }

        # Categorias padrão do buffet não exigem clique do cliente.
        for category_name in ("entradas", "churrasco", "saladas", "incluso"):
            category = by_name.get(category_name)
            if category:
                category.selection_mode = "info"
                category.min_choices = 0
                category.max_choices = 0
                category.choices_per_100 = 0

        sobremesas = by_name.get("sobremesas")
        if sobremesas:
            sobremesas.selection_mode = "multiple"
            sobremesas.min_choices = 0
            sobremesas.max_choices = 0
            sobremesas.choices_per_100 = 3
            if not sobremesas.selection_help:
                sobremesas.selection_help = "Escolha até 3 opções a cada 100 convidados."
            if not sobremesas.description:
                sobremesas.description = "Disponíveis nos pacotes que incluem sobremesa."

        # A categoria antiga 'Pratos principais' misturava itens fixos com escolhas.
        # Só desmembramos as linhas padrão conhecidas; qualquer item personalizado é preservado.
        pratos = by_name.get("pratos principais")
        if pratos:
            known_splits = {
                "macarrão: alho e óleo, carbonara ou molho sugo": (
                    "Massas",
                    ["Alho e óleo", "Carbonara", "Molho sugo"],
                    "Escolha 1 opção de massa.",
                    30,
                ),
                "strogonoff de carne ou frango": (
                    "Strogonoff",
                    ["Carne", "Frango"],
                    "Escolha carne ou frango.",
                    40,
                ),
                "lasanha: frango, bolonhesa, vegetariana ou quatro queijos": (
                    "Lasanha",
                    ["Frango", "Bolonhesa", "Vegetariana", "Quatro queijos"],
                    "Escolha 1 sabor.",
                    50,
                ),
            }
            for item in list(pratos.items):
                split = known_splits.get(item.name.strip().lower())
                if not split:
                    continue
                category_name, option_names, help_text, order = split
                target = _find_or_create_category(category_name, order)
                target.selection_mode = "single"
                target.selection_help = help_text
                target.min_choices = 1
                target.max_choices = 1
                target.choices_per_100 = 0
                for option_order, option_name in enumerate(option_names, start=1):
                    _add_item_if_missing(target, option_name, option_order)
                db.session.delete(item)

            pratos.selection_mode = "info"
            pratos.min_choices = 0
            pratos.max_choices = 0
            pratos.choices_per_100 = 0
            default_remaining = {
                "arroz branco",
                "arroz vegetariano, à grega ou campeiro",
                "aipim com bacon e queijo",
            }
            remaining_names = {item.name.strip().lower() for item in pratos.items}
            if remaining_names and remaining_names.issubset(default_remaining):
                pratos.name = "Acompanhamentos"
                pratos.description = "Itens do cardápio servidos conforme a composição do buffet."
                pratos.sort_order = 20

        # Ajusta texto das categorias padrão sem apagar conteúdo personalizado.
        churrasco = MenuCategory.query.filter(db.func.lower(MenuCategory.name) == "churrasco").first()
        if churrasco and not churrasco.description:
            churrasco.description = (
                "Seleção padrão do buffet: as variedades abaixo fazem parte do serviço e não precisam ser escolhidas."
            )
        saladas = MenuCategory.query.filter(db.func.lower(MenuCategory.name) == "saladas").first()
        if saladas and not saladas.description:
            saladas.description = "Servimos oito variedades, incluindo folhas, legumes e vinagrete."
        incluso = MenuCategory.query.filter(db.func.lower(MenuCategory.name) == "incluso").first()
        if incluso and not incluso.description:
            incluso.description = "Itens incluídos no serviço; não é necessário selecionar."

        current.menu_structure_version = 2
        db.session.flush()

    # Versão 3: vínculo explícito entre categoria e tipo de pacote. Isso substitui
    # a antiga dependência de procurar palavras como 'entrada'/'sobremesa' no nome.
    # Não altera regras de escolha nem flags dos pacotes já configuradas pelo admin.
    for category in MenuCategory.query.all():
        if category.package_feature not in MENU_PACKAGE_FEATURES:
            category.package_feature = "always"

    entradas = MenuCategory.query.filter(db.func.lower(MenuCategory.name) == "entradas").first()
    if entradas and (current.menu_structure_version or 0) < 3:
        entradas.package_feature = "entry"

    sobremesas = MenuCategory.query.filter(db.func.lower(MenuCategory.name) == "sobremesas").first()
    if sobremesas and (current.menu_structure_version or 0) < 3:
        sobremesas.package_feature = "dessert"

    current.menu_structure_version = 3
    db.session.flush()

    # Versão 4: aplica a estrutura final desejada para o Buffet do Marquinhos,
    # separando claramente o que é fixo do que o cliente realmente escolhe.
    if (current.menu_structure_version or 0) < 4:
        apply_recommended_menu_structure()
        current.menu_structure_version = 4

    db.session.commit()


def ensure_database() -> None:
    INSTANCE_DIR.mkdir(parents=True, exist_ok=True)
    UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
    # create_all cria tabelas faltantes; ensure_schema_updates cuida de bancos antigos.
    db.create_all()
    ensure_schema_updates()
    # Recarrega metadados/objetos após ALTER TABLE e então semeia apenas dados ausentes.
    seed_content()
    apply_data_migrations()


with app.app_context():
    ensure_database()


def site_content() -> SiteContent:
    current = SiteContent.query.first()
    if not current:
        current = default_site_content()
        db.session.add(current)
        db.session.commit()
    return current


def settings() -> Setting:
    current = Setting.query.first()
    if not current:
        current = Setting(max_events_per_day=2)
        db.session.add(current)
        db.session.commit()
    return current


def get_csrf_token() -> str:
    token = session.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["csrf_token"] = token
    return token


@app.before_request
def protect_admin_posts():
    if request.method == "POST" and request.path.startswith("/admin"):
        supplied = request.form.get("csrf_token", "")
        expected = session.get("csrf_token", "")
        if not supplied or not expected or not secrets.compare_digest(supplied, expected):
            abort(400, description="Token de segurança inválido. Atualize a página e tente novamente.")

        # Login/logout não alteram dados de negócio. Todas as demais gravações ficam
        # bloqueadas no Render até que o PostgreSQL persistente esteja conectado.
        if request.endpoint not in {"admin_login", "admin_logout"} and not PERSISTENCE_READY:
            flash(
                "Salvamento bloqueado por segurança: conecte o PostgreSQL persistente no Render "
                "antes de cadastrar ou alterar dados.",
                "error",
            )
            return redirect(url_for("admin_dashboard"))


@app.after_request
def add_security_headers(response):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; "
        "base-uri 'self'; "
        "object-src 'none'; "
        "frame-ancestors 'none'; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: blob:; "
        "connect-src 'self'; "
        "font-src 'self'; "
        "form-action 'self'",
    )
    if request.path.startswith("/admin"):
        response.headers["Cache-Control"] = "no-store, private"
    if RUNNING_ON_RENDER:
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return response


def safe_admin_referrer(default_endpoint: str = "admin_dashboard") -> str:
    """Retorna somente um referrer local do painel, evitando redirecionamento externo."""
    referrer = request.referrer or ""
    parsed = urlparse(referrer)
    same_host = not parsed.netloc or parsed.netloc == request.host
    if same_host and parsed.path.startswith("/admin"):
        target = parsed.path
        if parsed.query:
            target += f"?{parsed.query}"
        return target
    return url_for(default_endpoint)


@app.errorhandler(400)
def bad_request(error):
    if request.path.startswith("/admin"):
        description = getattr(error, "description", "Solicitação inválida.")
        flash(str(description), "error")
        destination = "admin_dashboard" if session.get("admin_logged_in") else "admin_login"
        return redirect(url_for(destination)), 400
    return jsonify({"error": "Solicitação inválida."}), 400


@app.errorhandler(413)
def upload_too_large(_error):
    flash(f"A imagem ultrapassa o limite de {MAX_UPLOAD_MB} MB.", "error")
    return redirect(safe_admin_referrer("admin_gallery"))


@app.errorhandler(SQLAlchemyError)
def database_error(error):
    db.session.rollback()
    app.logger.exception("Erro de banco de dados", exc_info=error)
    if request.path.startswith("/admin"):
        flash("O banco de dados ficou indisponível por alguns instantes. Nenhuma alteração parcial foi salva. Tente novamente.", "error")
        return redirect(safe_admin_referrer("admin_dashboard")), 503
    return jsonify({"error": "Serviço temporariamente indisponível."}), 503


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not PRODUCTION_SECRET_READY:
            abort(503, description="Configure SECRET_KEY no Render antes de usar o painel administrativo.")
        if not session.get("admin_logged_in"):
            return redirect(url_for("admin_login", next=request.path))
        return view(*args, **kwargs)

    return wrapped


def parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def parse_time(value: str | None):
    if not value:
        return None
    return datetime.strptime(value, "%H:%M").time()


def safe_int(value: str | None, default: int = 0) -> int:
    try:
        return int(value or default)
    except (TypeError, ValueError):
        return default


def normalized_package_feature(form) -> str:
    feature = (form.get("package_feature") or "always").strip().lower()
    return feature if feature in MENU_PACKAGE_FEATURES else "always"


def normalized_category_rules(form) -> tuple[str, int, int, int]:
    mode = (form.get("selection_mode") or "info").strip().lower()
    if mode not in MENU_SELECTION_MODES:
        mode = "info"

    if mode == "info":
        return mode, 0, 0, 0
    if mode == "single":
        return mode, 1, 1, 0

    min_choices = max(0, safe_int(form.get("min_choices"), 0))
    max_choices = max(0, safe_int(form.get("max_choices"), 0))
    choices_per_100 = max(0, safe_int(form.get("choices_per_100"), 0))
    if choices_per_100 > 0:
        # A regra por 100 substitui um teto fixo. O mínimo não pode tornar o
        # primeiro bloco de 100 impossível de preencher.
        max_choices = 0
        if min_choices > choices_per_100:
            raise ValueError("O mínimo não pode ser maior que o limite por 100 convidados.")
    elif max_choices > 0 and min_choices > max_choices:
        raise ValueError("A quantidade mínima não pode ser maior que a quantidade máxima.")
    return mode, min_choices, max_choices, choices_per_100


def database_storage_status() -> dict:
    backend = db.engine.url.get_backend_name()
    if backend == "postgresql":
        return {
            "kind": "PostgreSQL",
            "persistent": True,
            "message": "Dados administrativos armazenados em PostgreSQL persistente.",
        }
    database_path = str(db.engine.url.database or "")
    persistent_sqlite = database_path.startswith("/var/data/")
    if RUNNING_ON_RENDER:
        return {
            "kind": "SQLite",
            "persistent": False,
            "message": (
                "Modo de proteção ativo: o painel não permite salvar enquanto o PostgreSQL "
                "não estiver conectado."
            ),
        }
    return {
        "kind": "SQLite",
        "persistent": persistent_sqlite,
        "message": "Banco local de desenvolvimento.",
    }


def parse_decimal(value: str) -> Decimal:
    normalized = (value or "").strip().replace("R$", "").replace(" ", "")
    if "," in normalized and "." in normalized:
        normalized = normalized.replace(".", "").replace(",", ".")
    elif "," in normalized:
        normalized = normalized.replace(",", ".")
    amount = Decimal(normalized)
    if amount < 0:
        raise ValueError("O preço não pode ser negativo.")
    return amount


def digits_only(value: str) -> str:
    return re.sub(r"\D", "", value or "")


def valid_whatsapp_number(value: str) -> bool:
    digits = digits_only(value)
    return 12 <= len(digits) <= 15 and digits.startswith("55")


def normalize_instagram_handle(value: str) -> str:
    raw = (value or "").strip()
    raw = re.sub(r"^https?://(www\.)?instagram\.com/", "", raw, flags=re.IGNORECASE)
    raw = raw.split("?", 1)[0].strip("/ ")
    return raw.lstrip("@").strip()


def business_now() -> datetime:
    return datetime.now(BUSINESS_TZ)


def business_today() -> date:
    return business_now().date()


def month_from_query() -> tuple[int, int]:
    raw = request.args.get("mes")
    if raw:
        try:
            parsed = datetime.strptime(raw, "%Y-%m")
            return parsed.year, parsed.month
        except ValueError:
            pass
    today = business_today()
    return today.year, today.month


def add_months(year: int, month: int, delta: int) -> tuple[int, int]:
    zero_based = year * 12 + (month - 1) + delta
    return zero_based // 12, zero_based % 12 + 1


def active_event_count(day: date, exclude_event_id: int | None = None) -> int:
    query = Event.query.filter(Event.event_date == day, Event.status.in_(ACTIVE_STATUSES))
    if exclude_event_id is not None:
        query = query.filter(Event.id != exclude_event_id)
    return query.count()


def capacity_limit_for_write() -> int:
    """Serializa gravações de agenda no PostgreSQL para evitar ultrapassar a capacidade.

    Em produção, SELECT ... FOR UPDATE mantém a linha de configuração bloqueada até
    o commit/rollback do request. Assim dois cadastros simultâneos não validam a
    capacidade com o mesmo estado antigo. No SQLite local, usamos a consulta normal.
    """
    query = Setting.query
    if db.engine.url.get_backend_name() == "postgresql":
        query = query.with_for_update()
    current = query.first()
    if current is None:
        current = settings()
    return current.max_events_per_day


def availability(day: date) -> dict:
    max_events = settings().max_events_per_day
    blocked = BlockedDate.query.filter_by(blocked_date=day).first()
    count = active_event_count(day)
    remaining = max(max_events - count, 0)

    if day < business_today():
        status = "indisponivel"
        message = "Essa data já passou."
    elif blocked:
        status = "lotada"
        message = "Data indisponível para novos eventos."
    elif count >= max_events:
        status = "lotada"
        message = "Agenda lotada nesta data."
    elif remaining == 1:
        status = "ultima_vaga"
        message = "Última vaga disponível nesta data."
    else:
        status = "disponivel"
        message = "Temos disponibilidade nesta data."

    return {
        "date": day.isoformat(),
        "status": status,
        "message": message,
        "events": count,
        "remaining": remaining,
        "capacity": max_events,
        "blocked": bool(blocked),
    }


def image_url(storage: str, filename: str) -> str:
    if storage == "upload":
        return url_for("uploaded_file", filename=filename)
    return url_for("static", filename=filename)


def gallery_image_url(image: GalleryImage | None, fallback: str = "images/fogo-carne-2.webp") -> str:
    if image:
        return image_url(image.storage, image.filename)
    return url_for("static", filename=fallback)


def get_gallery_image(image_id: int | None) -> GalleryImage | None:
    if not image_id:
        return None
    return db.session.get(GalleryImage, image_id)


def save_uploaded_image(file_storage, prefix: str = "foto") -> str:
    original_name = secure_filename(file_storage.filename or "")
    extension = original_name.rsplit(".", 1)[-1].lower() if "." in original_name else ""
    if extension not in ALLOWED_IMAGE_EXTENSIONS:
        raise ValueError("Formato inválido. Envie JPG, PNG ou WEBP.")

    filename = f"{prefix}-{uuid.uuid4().hex}.webp"
    target = UPLOAD_ROOT / filename
    target.parent.mkdir(parents=True, exist_ok=True)

    try:
        # verify() valida a estrutura sem decodificar a imagem inteira. Depois
        # reabrimos o stream para aplicar rotação EXIF, reduzir e salvar em WEBP.
        with Image.open(file_storage.stream) as probe:
            width, height = probe.size
            if width <= 0 or height <= 0 or width * height > MAX_IMAGE_PIXELS:
                raise ValueError("A imagem é grande demais. Use uma foto de até 40 megapixels.")
            probe.verify()

        file_storage.stream.seek(0)
        with Image.open(file_storage.stream) as source:
            image = ImageOps.exif_transpose(source)
            if image.mode not in ("RGB", "RGBA"):
                image = image.convert("RGBA" if "transparency" in image.info else "RGB")
            image.thumbnail((2200, 2200), Image.Resampling.LANCZOS)
            image.save(target, "WEBP", quality=88, method=6)
    except ValueError:
        remove_upload(filename)
        raise
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        remove_upload(filename)
        raise ValueError("O arquivo enviado não é uma imagem válida ou não pôde ser processado.") from exc

    return filename


def remove_upload(filename: str) -> None:
    try:
        target = (UPLOAD_ROOT / filename).resolve()
        if target.parent == UPLOAD_ROOT and target.exists():
            target.unlink()
    except OSError:
        pass


def corporate_section() -> CorporateSection:
    current = CorporateSection.query.first()
    if not current:
        current = CorporateSection()
        db.session.add(current)
        db.session.commit()
    return current


def admin_template_context() -> dict:
    return {
        "site": site_content(),
        "corporate": corporate_section(),
        "storage_status": database_storage_status(),
    }


@app.get("/health")
def health():
    try:
        db.session.execute(text("SELECT 1"))
        storage = database_storage_status()
        return jsonify({
            "status": "ok",
            "database": storage["kind"],
            "persistent": storage["persistent"],
            "timezone": str(BUSINESS_TZ),
        }), 200
    except Exception:
        db.session.rollback()
        return jsonify({"status": "error"}), 503


@app.get("/")
def inicio():
    site = site_content()
    pricing_packages = PricingPackage.query.filter_by(active=True).order_by(PricingPackage.sort_order, PricingPackage.id).all()
    categories = MenuCategory.query.filter_by(active=True).order_by(MenuCategory.sort_order, MenuCategory.id).all()
    all_gallery_images = GalleryImage.query.filter_by(active=True).order_by(GalleryImage.sort_order, GalleryImage.id).all()
    category_rank = {"churrasco": 1, "pratos": 2, "saladas": 3, "sobremesas": 4}
    gallery = sorted(
        all_gallery_images,
        key=lambda image: (
            category_rank.get(image.category, 99),
            image.sort_order,
            image.id,
        ),
    )
    team_members = TeamMember.query.filter_by(active=True).order_by(TeamMember.sort_order, TeamMember.id).all()
    hero = get_gallery_image(site.hero_image_id)
    about_images = [
        get_gallery_image(site.about_image_1_id),
        get_gallery_image(site.about_image_2_id),
        get_gallery_image(site.about_image_3_id),
    ]
    return render_template(
        "index.html",
        site=site,
        pricing_packages=pricing_packages,
        menu_categories=categories,
        gallery_images=gallery,
        team_members=team_members,
        corporate=corporate_section(),
        gallery_categories=GALLERY_CATEGORIES,
        hero_image_url=gallery_image_url(hero),
        about_images=[
            gallery_image_url(about_images[0], "images/fogo-carne-1.webp"),
            gallery_image_url(about_images[1], "images/mesa-buffet.webp"),
            gallery_image_url(about_images[2], "images/sobremesa-maracuja.webp"),
        ],
        max_events_per_day=settings().max_events_per_day,
    )


@app.get("/uploads/<path:filename>")
def uploaded_file(filename: str):
    response = send_from_directory(UPLOAD_ROOT, filename)
    response.headers["Cache-Control"] = "public, max-age=604800"
    return response


@app.get("/api/disponibilidade")
def api_disponibilidade():
    raw = request.args.get("data", "")
    try:
        day = parse_date(raw)
    except ValueError:
        response = jsonify({"error": "Data inválida."})
        response.headers["Cache-Control"] = "no-store"
        return response, 400
    response = jsonify(availability(day))
    response.headers["Cache-Control"] = "no-store"
    return response


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        if not PRODUCTION_SECRET_READY:
            flash("Configure SECRET_KEY no Render antes de acessar o painel.", "error")
            return render_template("admin/login.html", **admin_template_context()), 503
        supplied = request.form.get("password", "")
        expected = os.getenv("ADMIN_PASSWORD")
        if not expected:
            if os.getenv("RENDER") == "true":
                flash("A senha administrativa ainda não foi configurada na hospedagem.", "error")
                return render_template("admin/login.html", **admin_template_context()), 503
            expected = "troque-esta-senha"
        if secrets.compare_digest(supplied, expected):
            session.clear()
            session["admin_logged_in"] = True
            session.permanent = True
            next_url = request.args.get("next", "")
            parsed = urlparse(next_url)
            if not next_url.startswith("/") or parsed.netloc:
                next_url = url_for("admin_dashboard")
            return redirect(next_url)
        flash("Senha incorreta.", "error")
    return render_template("admin/login.html", **admin_template_context())


@app.post("/admin/logout")
@admin_required
def admin_logout():
    session.clear()
    return redirect(url_for("admin_login"))


@app.get("/admin")
@admin_required
def admin_dashboard():
    year, month = month_from_query()
    cal = calendar.Calendar(firstweekday=6)
    weeks = []
    month_days = list(cal.itermonthdates(year, month))
    start, end = month_days[0], month_days[-1]

    events = Event.query.filter(Event.event_date.between(start, end)).order_by(Event.event_date, Event.event_time).all()
    blocked_dates = BlockedDate.query.filter(BlockedDate.blocked_date.between(start, end)).all()
    events_by_day: dict[date, list[Event]] = {}
    for event in events:
        events_by_day.setdefault(event.event_date, []).append(event)
    blocked_by_day = {item.blocked_date: item for item in blocked_dates}

    for week in cal.monthdatescalendar(year, month):
        row = []
        for day in week:
            day_events = events_by_day.get(day, [])
            active_count = sum(1 for event in day_events if event.counts_toward_capacity)
            info = availability(day)
            row.append({
                "date": day,
                "in_month": day.month == month,
                "events": day_events,
                "active_count": active_count,
                "status": info["status"],
                "blocked": blocked_by_day.get(day),
            })
        weeks.append(row)

    previous = add_months(year, month, -1)
    following = add_months(year, month, 1)
    today = business_today()
    upcoming = Event.query.filter(Event.event_date >= today, Event.status.in_(ACTIVE_STATUSES)).order_by(Event.event_date, Event.event_time).limit(8).all()

    month_names = ["", "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
    return render_template(
        "admin/dashboard.html",
        weeks=weeks,
        year=year,
        month=month,
        month_name=month_names[month],
        previous=f"{previous[0]:04d}-{previous[1]:02d}",
        following=f"{following[0]:04d}-{following[1]:02d}",
        upcoming=upcoming,
        current_settings=settings(),
        status_labels=STATUS_LABELS,
        today=today,
        active_page="agenda",
        **admin_template_context(),
    )


@app.post("/admin/eventos/novo")
@admin_required
def admin_new_event():
    try:
        event_date = parse_date(request.form.get("event_date", ""))
        event_time = parse_time(request.form.get("event_time"))
        status = request.form.get("status", "reservado")
        if status not in STATUS_LABELS:
            raise ValueError("Status inválido")
        if status in ACTIVE_STATUSES:
            max_events = capacity_limit_for_write()
            if BlockedDate.query.filter_by(blocked_date=event_date).first():
                flash("Esta data está bloqueada. Desbloqueie-a antes de cadastrar o evento.", "error")
                return redirect(url_for("admin_dashboard", mes=event_date.strftime("%Y-%m")))
            if active_event_count(event_date) >= max_events:
                flash("A capacidade máxima de eventos para essa data já foi atingida.", "error")
                return redirect(url_for("admin_dashboard", mes=event_date.strftime("%Y-%m")))

        event = Event(
            event_date=event_date,
            event_time=event_time,
            client_name=request.form.get("client_name", "").strip(),
            phone=request.form.get("phone", "").strip(),
            city=request.form.get("city", "Praia Grande").strip() or "Praia Grande",
            venue=request.form.get("venue", "").strip(),
            guests=int(request.form["guests"]) if request.form.get("guests") else None,
            event_type=request.form.get("event_type", "").strip(),
            menu=request.form.get("menu", "").strip(),
            status=status,
            notes=request.form.get("notes", "").strip(),
        )
        if not event.client_name:
            raise ValueError("Informe o nome do cliente")
        if event.guests is not None and event.guests < 1:
            raise ValueError("O número de convidados deve ser maior que zero")
        db.session.add(event)
        db.session.commit()
        flash("Evento cadastrado com sucesso.", "success")
        return redirect(url_for("admin_dashboard", mes=event_date.strftime("%Y-%m")))
    except (ValueError, KeyError):
        db.session.rollback()
        flash("Confira os dados obrigatórios do evento.", "error")
        return redirect(url_for("admin_dashboard"))


@app.route("/admin/eventos/<int:event_id>/editar", methods=["GET", "POST"])
@admin_required
def admin_edit_event(event_id: int):
    event = Event.query.get_or_404(event_id)
    if request.method == "POST":
        try:
            new_date = parse_date(request.form.get("event_date", ""))
            new_status = request.form.get("status", "reservado")
            if new_status not in STATUS_LABELS:
                raise ValueError("Status inválido")
            if new_status in ACTIVE_STATUSES:
                max_events = capacity_limit_for_write()
                blocked = BlockedDate.query.filter_by(blocked_date=new_date).first()
                if blocked and new_date != event.event_date:
                    flash("A nova data está bloqueada.", "error")
                    return redirect(url_for("admin_edit_event", event_id=event.id))
                if active_event_count(new_date, exclude_event_id=event.id) >= max_events:
                    flash("A nova data já atingiu a capacidade máxima.", "error")
                    return redirect(url_for("admin_edit_event", event_id=event.id))

            event.event_date = new_date
            event.event_time = parse_time(request.form.get("event_time"))
            event.client_name = request.form.get("client_name", "").strip()
            event.phone = request.form.get("phone", "").strip()
            event.city = request.form.get("city", "Praia Grande").strip() or "Praia Grande"
            event.venue = request.form.get("venue", "").strip()
            event.guests = int(request.form["guests"]) if request.form.get("guests") else None
            event.event_type = request.form.get("event_type", "").strip()
            event.menu = request.form.get("menu", "").strip()
            event.status = new_status
            event.notes = request.form.get("notes", "").strip()
            if not event.client_name:
                raise ValueError("Informe o nome do cliente")
            if event.guests is not None and event.guests < 1:
                raise ValueError("O número de convidados deve ser maior que zero")
            db.session.commit()
            flash("Evento atualizado.", "success")
            return redirect(url_for("admin_dashboard", mes=new_date.strftime("%Y-%m")))
        except (ValueError, KeyError):
            db.session.rollback()
            flash("Não foi possível atualizar. Confira os campos.", "error")
    return render_template("admin/edit_event.html", event=event, status_labels=STATUS_LABELS, active_page="agenda", **admin_template_context())


@app.post("/admin/eventos/<int:event_id>/excluir")
@admin_required
def admin_delete_event(event_id: int):
    event = Event.query.get_or_404(event_id)
    target_month = event.event_date.strftime("%Y-%m")
    db.session.delete(event)
    db.session.commit()
    flash("Evento excluído.", "success")
    return redirect(url_for("admin_dashboard", mes=target_month))


@app.post("/admin/datas/bloquear")
@admin_required
def admin_block_date():
    try:
        blocked_date = parse_date(request.form.get("blocked_date", ""))
        capacity_limit_for_write()  # serializa com cadastros/edições de evento concorrentes
        item = BlockedDate.query.filter_by(blocked_date=blocked_date).first()
        if not item:
            item = BlockedDate(blocked_date=blocked_date)
            db.session.add(item)
        item.reason = request.form.get("reason", "").strip()
        db.session.commit()
        flash("Data bloqueada para novos eventos.", "success")
        return redirect(url_for("admin_dashboard", mes=blocked_date.strftime("%Y-%m")))
    except ValueError:
        flash("Informe uma data válida.", "error")
        return redirect(url_for("admin_dashboard"))


@app.post("/admin/datas/<int:block_id>/desbloquear")
@admin_required
def admin_unblock_date(block_id: int):
    item = BlockedDate.query.get_or_404(block_id)
    target_month = item.blocked_date.strftime("%Y-%m")
    db.session.delete(item)
    db.session.commit()
    flash("Data desbloqueada.", "success")
    return redirect(url_for("admin_dashboard", mes=target_month))


@app.post("/admin/configuracoes")
@admin_required
def admin_settings():
    try:
        max_events = int(request.form.get("max_events_per_day", "2"))
        if not 1 <= max_events <= 10:
            raise ValueError
        current = settings()
        current.max_events_per_day = max_events
        db.session.commit()
        flash("Capacidade diária atualizada.", "success")
    except ValueError:
        flash("Escolha uma capacidade entre 1 e 10 eventos por dia.", "error")
    return redirect(url_for("admin_dashboard"))


@app.get("/admin/conteudo")
@admin_required
def admin_content():
    packages = PricingPackage.query.order_by(PricingPackage.sort_order, PricingPackage.id).all()
    return render_template("admin/content.html", packages=packages, active_page="conteudo", **admin_template_context())


@app.post("/admin/conteudo/salvar")
@admin_required
def admin_save_content():
    site = site_content()
    text_fields = [
        "brand_name", "page_title", "meta_description", "hero_badge", "hero_title", "hero_highlight",
        "hero_description", "story_eyebrow", "story_title", "story_highlight", "story_text",
        "pricing_eyebrow", "pricing_title", "pricing_description", "pricing_notice", "dessert_notice", "travel_notice",
        "menu_eyebrow", "menu_title", "menu_description", "availability_eyebrow", "availability_title",
        "availability_description", "gallery_eyebrow", "gallery_title", "contact_eyebrow", "contact_title",
        "contact_description", "base_city", "whatsapp_display", "address", "cnpj",
        "footer_tagline",
    ]
    for field in text_fields:
        value = request.form.get(field, "").strip()
        if value:
            setattr(site, field, value)
    submitted_whatsapp = digits_only(request.form.get("whatsapp_number", site.whatsapp_number))
    if valid_whatsapp_number(submitted_whatsapp):
        site.whatsapp_number = submitted_whatsapp
    else:
        flash("O WhatsApp deve conter 55 + DDD + número. O número anterior foi mantido.", "error")

    submitted_instagram = normalize_instagram_handle(request.form.get("instagram_handle", site.instagram_handle))
    if submitted_instagram:
        site.instagram_handle = submitted_instagram

    site.since_year = max(1900, min(business_today().year, safe_int(request.form.get("since_year"), site.since_year)))

    corporate = corporate_section()
    for field in ["eyebrow", "title", "highlight", "description"]:
        value = request.form.get(f"corporate_{field}", "").strip()
        if value:
            setattr(corporate, field, value)

    db.session.commit()
    flash("Textos e contatos atualizados no site.", "success")
    return redirect(url_for("admin_content"))


@app.post("/admin/conteudo/logo")
@admin_required
def admin_upload_logo():
    site = site_content()
    file_storage = request.files.get("logo")
    if not file_storage or not file_storage.filename:
        flash("Escolha uma imagem para o logo.", "error")
        return redirect(url_for("admin_content"))
    try:
        filename = save_uploaded_image(file_storage, prefix="logo")
        old_upload = site.logo_filename if site.logo_storage == "upload" else None
        site.logo_storage = "upload"
        site.logo_filename = filename
        try:
            db.session.commit()
        except SQLAlchemyError:
            db.session.rollback()
            remove_upload(filename)
            raise
        if old_upload and old_upload != filename:
            remove_upload(old_upload)
        flash("Logo atualizado.", "success")
    except ValueError as exc:
        flash(str(exc), "error")
    return redirect(url_for("admin_content"))


@app.post("/admin/conteudo/cardapio-oficial")
@admin_required
def admin_upload_official_menu():
    site = site_content()
    file_storage = request.files.get("official_menu")
    if not file_storage or not file_storage.filename:
        flash("Escolha uma imagem do cardápio.", "error")
        return redirect(url_for("admin_content"))
    try:
        filename = save_uploaded_image(file_storage, prefix="cardapio")
        old_upload = site.official_menu_filename if site.official_menu_storage == "upload" else None
        site.official_menu_storage = "upload"
        site.official_menu_filename = filename
        try:
            db.session.commit()
        except SQLAlchemyError:
            db.session.rollback()
            remove_upload(filename)
            raise
        if old_upload and old_upload != filename:
            remove_upload(old_upload)
        flash("Imagem do cardápio oficial atualizada.", "success")
    except ValueError as exc:
        flash(str(exc), "error")
    return redirect(url_for("admin_content"))


@app.post("/admin/precos/novo")
@admin_required
def admin_new_package():
    try:
        name = request.form.get("name", "").strip()
        if not name:
            raise ValueError("Informe o nome do pacote.")
        package = PricingPackage(
            name=name,
            price=parse_decimal(request.form.get("price", "")),
            description=request.form.get("description", "").strip(),
            badge=request.form.get("badge", "").strip() or None,
            includes_entry=request.form.get("includes_entry") == "on",
            includes_dessert=request.form.get("includes_dessert") == "on",
            featured=request.form.get("featured") == "on",
            active=request.form.get("active") == "on",
            sort_order=safe_int(request.form.get("sort_order"), 0),
        )
        db.session.add(package)
        db.session.commit()
        flash("Pacote adicionado.", "success")
    except (ValueError, InvalidOperation) as exc:
        db.session.rollback()
        flash(str(exc) or "Preço inválido.", "error")
    return redirect(url_for("admin_content") + "#precos")


@app.post("/admin/precos/<int:package_id>/salvar")
@admin_required
def admin_save_package(package_id: int):
    package = PricingPackage.query.get_or_404(package_id)
    try:
        package.name = request.form.get("name", "").strip()
        if not package.name:
            raise ValueError("Informe o nome do pacote.")
        package.price = parse_decimal(request.form.get("price", ""))
        package.description = request.form.get("description", "").strip()
        package.badge = request.form.get("badge", "").strip() or None
        package.includes_entry = request.form.get("includes_entry") == "on"
        package.includes_dessert = request.form.get("includes_dessert") == "on"
        package.featured = request.form.get("featured") == "on"
        package.active = request.form.get("active") == "on"
        package.sort_order = safe_int(request.form.get("sort_order"), 0)
        db.session.commit()
        flash("Pacote atualizado.", "success")
    except (ValueError, InvalidOperation) as exc:
        db.session.rollback()
        flash(str(exc) or "Preço inválido.", "error")
    return redirect(url_for("admin_content") + "#precos")


@app.post("/admin/precos/<int:package_id>/excluir")
@admin_required
def admin_delete_package(package_id: int):
    package = PricingPackage.query.get_or_404(package_id)
    db.session.delete(package)
    db.session.commit()
    flash("Pacote excluído.", "success")
    return redirect(url_for("admin_content") + "#precos")


@app.get("/admin/cardapio")
@admin_required
def admin_menu():
    categories = MenuCategory.query.order_by(MenuCategory.sort_order, MenuCategory.id).all()
    return render_template(
        "admin/menu.html",
        categories=categories,
        selection_modes=MENU_SELECTION_MODES,
        package_features=MENU_PACKAGE_FEATURES,
        active_page="cardapio",
        **admin_template_context(),
    )


@app.post("/admin/cardapio/aplicar-estrutura-recomendada")
@admin_required
def admin_apply_recommended_menu():
    try:
        apply_recommended_menu_structure()
        current = Setting.query.first()
        if not current:
            current = Setting(max_events_per_day=2, bootstrap_version=1, menu_structure_version=4)
            db.session.add(current)
        current.menu_structure_version = max(current.menu_structure_version or 0, 4)
        db.session.commit()
        flash("Estrutura recomendada do cardápio aplicada com sucesso.", "success")
    except Exception as exc:
        db.session.rollback()
        flash(str(exc) or "Não foi possível aplicar a estrutura recomendada.", "error")
    return redirect(url_for("admin_menu"))


@app.post("/admin/cardapio/categorias/nova")
@admin_required
def admin_new_category():
    name = request.form.get("name", "").strip()
    if not name:
        flash("Informe o nome da categoria.", "error")
        return redirect(url_for("admin_menu"))

    try:
        mode, min_choices, max_choices, choices_per_100 = normalized_category_rules(request.form)
        category = MenuCategory(
            name=name,
            description=request.form.get("description", "").strip() or None,
            selection_mode=mode,
            selection_help=request.form.get("selection_help", "").strip() or None,
            package_feature=normalized_package_feature(request.form),
            min_choices=min_choices,
            max_choices=max_choices,
            choices_per_100=choices_per_100,
            active=request.form.get("active") == "on",
            sort_order=safe_int(request.form.get("sort_order"), 0),
        )
        db.session.add(category)
        db.session.commit()
        flash("Categoria adicionada.", "success")
    except ValueError as exc:
        db.session.rollback()
        flash(str(exc), "error")
    return redirect(url_for("admin_menu"))


@app.post("/admin/cardapio/categorias/<int:category_id>/salvar")
@admin_required
def admin_save_category(category_id: int):
    category = MenuCategory.query.get_or_404(category_id)
    name = request.form.get("name", "").strip()
    if not name:
        flash("Informe o nome da categoria.", "error")
        return redirect(url_for("admin_menu") + f"#categoria-{category_id}")

    try:
        mode, min_choices, max_choices, choices_per_100 = normalized_category_rules(request.form)
        category.name = name
        category.description = request.form.get("description", "").strip() or None
        category.selection_mode = mode
        category.selection_help = request.form.get("selection_help", "").strip() or None
        category.package_feature = normalized_package_feature(request.form)
        category.min_choices = min_choices
        category.max_choices = max_choices
        category.choices_per_100 = choices_per_100
        category.active = request.form.get("active") == "on"
        category.sort_order = safe_int(request.form.get("sort_order"), 0)
        db.session.commit()
        flash("Categoria atualizada.", "success")
    except ValueError as exc:
        db.session.rollback()
        flash(str(exc), "error")
    return redirect(url_for("admin_menu") + f"#categoria-{category_id}")


@app.post("/admin/cardapio/categorias/<int:category_id>/excluir")
@admin_required
def admin_delete_category(category_id: int):
    category = MenuCategory.query.get_or_404(category_id)
    db.session.delete(category)
    db.session.commit()
    flash("Categoria e seus itens foram excluídos.", "success")
    return redirect(url_for("admin_menu"))


@app.post("/admin/cardapio/categorias/<int:category_id>/itens/novo")
@admin_required
def admin_new_menu_item(category_id: int):
    # O ID da categoria vem na própria URL. Isso evita que o formulário
    # perca ou envie um category_id incorreto e termine em um 404 genérico.
    category = db.session.get(MenuCategory, category_id)
    if category is None:
        flash("A categoria selecionada não foi encontrada. Atualize a página e tente novamente.", "error")
        return redirect(url_for("admin_menu"))

    name = request.form.get("name", "").strip()
    if not name:
        flash("Informe o nome do item.", "error")
    else:
        db.session.add(MenuItem(
            category_id=category.id,
            name=name,
            active=request.form.get("active") == "on",
            sort_order=safe_int(request.form.get("sort_order"), 0),
        ))
        db.session.commit()
        flash("Item adicionado ao cardápio.", "success")
    return redirect(url_for("admin_menu") + f"#categoria-{category.id}")


@app.post("/admin/cardapio/itens/<int:item_id>/salvar")
@admin_required
def admin_save_menu_item(item_id: int):
    item = MenuItem.query.get_or_404(item_id)
    name = request.form.get("name", "").strip()
    if not name:
        flash("Informe o nome do item.", "error")
    else:
        item.name = name
        item.active = request.form.get("active") == "on"
        item.sort_order = safe_int(request.form.get("sort_order"), 0)
        new_category_id = safe_int(request.form.get("category_id"), item.category_id)
        if db.session.get(MenuCategory, new_category_id):
            item.category_id = new_category_id
        db.session.commit()
        flash("Item atualizado.", "success")
    return redirect(url_for("admin_menu") + f"#categoria-{item.category_id}")


@app.post("/admin/cardapio/itens/<int:item_id>/excluir")
@admin_required
def admin_delete_menu_item(item_id: int):
    item = MenuItem.query.get_or_404(item_id)
    category_id = item.category_id
    db.session.delete(item)
    db.session.commit()
    flash("Item excluído.", "success")
    return redirect(url_for("admin_menu") + f"#categoria-{category_id}")


@app.get("/admin/galeria")
@admin_required
def admin_gallery():
    images = GalleryImage.query.order_by(GalleryImage.sort_order, GalleryImage.id).all()
    return render_template(
        "admin/gallery.html",
        images=images,
        gallery_categories=GALLERY_CATEGORIES,
        active_page="galeria",
        **admin_template_context(),
    )


@app.post("/admin/galeria/enviar")
@admin_required
def admin_upload_gallery():
    files = [file for file in request.files.getlist("photos") if file and file.filename]
    category = request.form.get("category", "pratos")
    if category not in GALLERY_CATEGORIES:
        category = "pratos"
    if not files:
        flash("Escolha pelo menos uma foto.", "error")
        return redirect(url_for("admin_gallery"))

    added = 0
    errors = []
    saved_filenames: list[str] = []
    next_order = (db.session.query(db.func.max(GalleryImage.sort_order)).scalar() or 0) + 1
    for file_storage in files:
        try:
            filename = save_uploaded_image(file_storage, prefix="galeria")
            saved_filenames.append(filename)
            db.session.add(GalleryImage(storage="upload", filename=filename, category=category, active=True, sort_order=next_order))
            next_order += 1
            added += 1
        except ValueError as exc:
            errors.append(f"{file_storage.filename}: {exc}")
    try:
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        # Se o banco falhar, remove os arquivos que ainda não possuem registro válido.
        for filename in saved_filenames:
            remove_upload(filename)
        raise
    if added:
        flash(f"{added} foto(s) adicionada(s) à galeria.", "success")
    if errors:
        flash(" | ".join(errors), "error")
    return redirect(url_for("admin_gallery"))


@app.post("/admin/galeria/<int:image_id>/salvar")
@admin_required
def admin_save_gallery_image(image_id: int):
    image = GalleryImage.query.get_or_404(image_id)
    category = request.form.get("category", image.category)
    if category in GALLERY_CATEGORIES:
        image.category = category
    image.active = request.form.get("active") == "on"
    image.sort_order = safe_int(request.form.get("sort_order"), image.sort_order)
    db.session.commit()
    flash("Foto atualizada.", "success")
    return redirect(url_for("admin_gallery") + f"#foto-{image.id}")


@app.post("/admin/galeria/destaques")
@admin_required
def admin_gallery_roles():
    site = site_content()
    valid_ids = {image.id for image in GalleryImage.query.all()}
    for field in ["hero_image_id", "about_image_1_id", "about_image_2_id", "about_image_3_id"]:
        value = safe_int(request.form.get(field), 0)
        setattr(site, field, value if value in valid_ids else None)
    db.session.commit()
    flash("Fotos de destaque atualizadas.", "success")
    return redirect(url_for("admin_gallery"))


@app.post("/admin/galeria/<int:image_id>/excluir")
@admin_required
def admin_delete_gallery_image(image_id: int):
    image = GalleryImage.query.get_or_404(image_id)
    site = site_content()
    for field in ["hero_image_id", "about_image_1_id", "about_image_2_id", "about_image_3_id"]:
        if getattr(site, field) == image.id:
            setattr(site, field, None)
    upload_to_remove = image.filename if image.storage == "upload" else None
    db.session.delete(image)
    db.session.commit()
    if upload_to_remove:
        remove_upload(upload_to_remove)
    flash("Foto excluída.", "success")
    return redirect(url_for("admin_gallery"))



@app.get("/admin/equipe")
@admin_required
def admin_team():
    members = TeamMember.query.order_by(TeamMember.sort_order, TeamMember.id).all()
    return render_template(
        "admin/team.html",
        members=members,
        active_page="equipe",
        **admin_template_context(),
    )


@app.post("/admin/equipe/novo")
@admin_required
def admin_new_team_member():
    name = request.form.get("name", "").strip()
    if not name:
        flash("Informe o nome do integrante.", "error")
        return redirect(url_for("admin_team"))

    member = TeamMember(
        name=name,
        role=request.form.get("role", "").strip(),
        bio=request.form.get("bio", "").strip(),
        image_storage="static",
        image_filename="images/equipe-placeholder.webp",
        active=request.form.get("active") == "on",
        sort_order=safe_int(request.form.get("sort_order"), 0),
    )

    file_storage = request.files.get("photo")
    if file_storage and file_storage.filename:
        try:
            member.image_filename = save_uploaded_image(file_storage, prefix="equipe")
            member.image_storage = "upload"
        except ValueError as exc:
            flash(str(exc), "error")
            return redirect(url_for("admin_team"))

    db.session.add(member)
    try:
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        if member.image_storage == "upload":
            remove_upload(member.image_filename)
        raise
    flash("Integrante adicionado à seção Quem somos.", "success")
    return redirect(url_for("admin_team"))


@app.post("/admin/equipe/<int:member_id>/salvar")
@admin_required
def admin_save_team_member(member_id: int):
    member = TeamMember.query.get_or_404(member_id)
    name = request.form.get("name", "").strip()
    if not name:
        flash("Informe o nome do integrante.", "error")
        return redirect(url_for("admin_team") + f"#integrante-{member.id}")

    member.name = name
    member.role = request.form.get("role", "").strip()
    member.bio = request.form.get("bio", "").strip()
    member.active = request.form.get("active") == "on"
    member.sort_order = safe_int(request.form.get("sort_order"), member.sort_order)

    file_storage = request.files.get("photo")
    new_filename = None
    old_upload = None
    if file_storage and file_storage.filename:
        try:
            new_filename = save_uploaded_image(file_storage, prefix="equipe")
            old_upload = member.image_filename if member.image_storage == "upload" else None
            member.image_storage = "upload"
            member.image_filename = new_filename
        except ValueError as exc:
            flash(str(exc), "error")
            return redirect(url_for("admin_team") + f"#integrante-{member.id}")

    try:
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        if new_filename:
            remove_upload(new_filename)
        raise
    if old_upload and old_upload != new_filename:
        remove_upload(old_upload)
    flash("Integrante atualizado.", "success")
    return redirect(url_for("admin_team") + f"#integrante-{member.id}")


@app.post("/admin/equipe/<int:member_id>/excluir")
@admin_required
def admin_delete_team_member(member_id: int):
    member = TeamMember.query.get_or_404(member_id)
    upload_to_remove = member.image_filename if member.image_storage == "upload" else None
    db.session.delete(member)
    db.session.commit()
    if upload_to_remove:
        remove_upload(upload_to_remove)
    flash("Integrante excluído.", "success")
    return redirect(url_for("admin_team"))


@app.context_processor
def inject_globals():
    site = site_content()
    return {
        "current_year": business_now().year,
        "csrf_token": get_csrf_token,
        "image_url": image_url,
        "gallery_image_url": gallery_image_url,
        "money_br": lambda value: f"{Decimal(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
    }


if __name__ == "__main__":
    app.run(debug=os.getenv("FLASK_DEBUG") == "1", host="0.0.0.0", port=int(os.getenv("PORT", "5000")))
