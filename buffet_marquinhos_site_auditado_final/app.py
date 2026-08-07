from __future__ import annotations

import calendar
import os
import re
import secrets
import uuid
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from functools import wraps
from pathlib import Path
from urllib.parse import urlparse

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
from werkzeug.utils import secure_filename

BASE_DIR = Path(__file__).resolve().parent
INSTANCE_DIR = BASE_DIR / "instance"
DEFAULT_DB = "sqlite:///" + str(INSTANCE_DIR / "buffet.db")
DATABASE_URL = os.getenv("DATABASE_URL", DEFAULT_DB)
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

UPLOAD_ROOT = Path(os.getenv("UPLOAD_ROOT", str(BASE_DIR / "static" / "uploads"))).resolve()
MAX_UPLOAD_MB = 12
ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}

app = Flask(__name__)
app.config.update(
    SECRET_KEY=os.getenv("SECRET_KEY", "desenvolvimento-troque-esta-chave"),
    SQLALCHEMY_DATABASE_URI=DATABASE_URL,
    SQLALCHEMY_TRACK_MODIFICATIONS=False,
    MAX_CONTENT_LENGTH=MAX_UPLOAD_MB * 1024 * 1024,
    PERMANENT_SESSION_LIFETIME=60 * 60 * 12,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.getenv("RENDER") == "true" or os.getenv("HTTPS_ONLY") == "1",
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


class Setting(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    max_events_per_day = db.Column(db.Integer, nullable=False, default=2)


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
    featured = db.Column(db.Boolean, nullable=False, default=False)
    active = db.Column(db.Boolean, nullable=False, default=True)
    sort_order = db.Column(db.Integer, nullable=False, default=0)


class MenuCategory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.String(240), nullable=True)
    min_choices = db.Column(db.Integer, nullable=false, default=0)
    max_choices = db.Column(db.integer, nullable=true)
    required = db.column(db.boolean, nullable=false, default=false)
    selection_help = db.Column(db.string(420), nullable=true)
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
        menu_eyebrow="Cardápio personalizável",
        menu_title="Monte uma experiência com a sua cara.",
        menu_description=(
            "As opções podem ser combinadas conforme o perfil e o tamanho do evento. "
            "Além do cardápio apresentado, também elaboramos cardápios personalizados "
            "de acordo com o gosto do cliente, com possibilidade de incluir pratos que "
            "não estejam no cardápio padrão, mediante consulta e orçamento."
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
    if not Setting.query.first():
        db.session.add(Setting(max_events_per_day=2))

    site = SiteContent.query.first()
    if not site:
        site = default_site_content()
        db.session.add(site)
        db.session.flush()

    if site.menu_description == 'As opções podem ser combinadas conforme o perfil e o tamanho do evento.':
        site.menu_description = 'As opções podem ser combinadas conforme o perfil e o tamanho do evento. Além do cardápio apresentado, também elaboramos cardápios personalizados de acordo com o gosto do cliente, com possibilidade de incluir pratos que não estejam no cardápio padrão, mediante consulta e orçamento.'

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
    elif team_section.eyebrow == "Clientes e eventos":
        team_section.eyebrow = "Quem somos"
        team_section.title = "Pessoas que fazem"
        team_section.highlight = "tudo acontecer."
        team_section.description = (
            "Por trás de cada evento existe uma equipe dedicada ao preparo, à organização "
            "e ao atendimento. Conheça as pessoas que fazem parte da história do Buffet do "
            "Marquinhos e trabalham para que cada celebração seja conduzida com cuidado."
        )

    if PricingPackage.query.count() == 0:
        packages = [
            PricingPackage(name="Entrada + sobremesa", price=Decimal("80.00"), description="Inclui entrada, pratos principais, churrasco, saladas e sobremesas.", badge="Completo", featured=True, sort_order=1),
            PricingPackage(name="Com entrada", price=Decimal("74.00"), description="Entrada, pratos principais, churrasco e saladas.", sort_order=2),
            PricingPackage(name="Com sobremesa", price=Decimal("73.00"), description="Pratos principais, churrasco, saladas e sobremesas.", sort_order=3),
            PricingPackage(name="Buffet essencial", price=Decimal("67.00"), description="Sem entrada e sem sobremesa.", sort_order=4),
        ]
        db.session.add_all(packages)

    if MenuCategory.query.count() == 0:
        menu_seed = [
            ("Entradas", ["Risoto de alho-poró", "Escondidinho de carne-seca com aipim"]),
            ("Pratos principais", [
                "Arroz branco",
                "Arroz vegetariano, à grega ou campeiro",
                "Aipim com bacon e queijo",
                "Macarrão: alho e óleo, carbonara ou molho sugo",
                "Strogonoff de carne ou frango",
                "Lasanha: frango, bolonhesa, vegetariana ou quatro queijos",
            ]),
            ("Churrasco", ["Entrecot, vazio e maminha", "Costelinha suína", "Sobrecoxa de frango", "Salsichão colonial", "Abacaxi com canela"]),
            ("Saladas", ["Oito variedades", "Folhas, legumes e vinagrete", "Opções adaptadas à composição do evento"]),
            ("Sobremesas", ["Mousses: maracujá, uva e Ninho", "Bombom de travessa", "Doce sensação", "Manjar de ameixa", "Abacaxi com creme branco", "Pavê de Sonho de Valsa", "Torta de bolacha"]),
            ("Incluso", ["Taças", "Pratos", "Talheres em inox", "Guardanapos de papel"]),
        ]
        for category_order, (category_name, items) in enumerate(menu_seed, start=1):
            category = MenuCategory(name=category_name, sort_order=category_order)
            db.session.add(category)
            db.session.flush()
            for item_order, item_name in enumerate(items, start=1):
                db.session.add(MenuItem(category_id=category.id, name=item_name, sort_order=item_order))

    if GalleryImage.query.count() == 0:
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
        legacy_photo = GalleryImage.query.filter_by(
            storage="static",
            filename=old_filename,
            category="pratos",
        ).first()
        if legacy_photo:
            legacy_photo.filename = new_filename

    for legacy_image in GalleryImage.query.filter_by(category="clientes").all():
        db.session.delete(legacy_image)

    if TeamMember.query.count() == 0:
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
    else:
        # Atualiza automaticamente a seção em instalações que já possuam banco de dados.
        marquinhos_member = TeamMember.query.filter_by(name="Marquinhos").first()
        if marquinhos_member and marquinhos_member.image_storage == "static":
            marquinhos_member.role = "Proprietário e fundador"
            marquinhos_member.bio = (
                "À frente do buffet, acompanha a preparação, a organização e a realização de cada evento."
            )
            marquinhos_member.image_filename = "images/equipe-marquinhos.webp"
            marquinhos_member.sort_order = 1

        virginia_member = TeamMember.query.filter_by(name="Virgínia").first()
        if virginia_member and virginia_member.image_storage == "static":
            virginia_member.role = "Proprietária, fundadora e responsável pela cozinha"
            virginia_member.bio = (
                "Participa da preparação e da organização dos eventos, coordenando a cozinha "
                "e sendo responsável pela elaboração dos alimentos do buffet, para que cada "
                "serviço seja conduzido com cuidado, qualidade e dedicação."
            )
            virginia_member.image_filename = "images/equipe-virginia.webp"
            virginia_member.sort_order = 2

        team_member = TeamMember.query.filter_by(name="Equipe do Buffet do Marquinhos").first()
        if team_member and team_member.image_storage == "static":
            team_member.role = "Preparo, organização e atendimento dos eventos"
            team_member.bio = (
                "Uma equipe comprometida com a cozinha, o churrasco, a montagem e o atendimento, "
                "trabalhando em conjunto para oferecer uma experiência acolhedora aos convidados."
            )
            team_member.image_filename = "images/equipe-grupo.webp"
            team_member.sort_order = 3

    db.session.commit()


def ensure_schema_updates() -> None:
    # Mantém compatibilidade caso o site já tenha sido iniciado antes desta atualização.
    inspector = inspect(db.engine)
    if "site_content" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("site_content")}
    if "dessert_notice" not in columns:
        with db.engine.begin() as connection:
            connection.execute(text("ALTER TABLE site_content ADD COLUMN dessert_notice TEXT"))
            connection.execute(
                text(
                    "UPDATE site_content SET dessert_notice = :notice "
                    "WHERE dessert_notice IS NULL OR dessert_notice = ''"
                ),
                {"notice": "São disponibilizadas 3 opções de sobremesas a cada 100 convidados."},
            )


    menu_columns = {column["name"] for column in inspector.get_columns("menu_category")}

    with db.engine.begin() as connection:
        if "min_choices" not in menu_columns:
            connection.execute(
                text("ALTER TABLE menu_category ADD COLUMN min_choices INTEGER NOT NULL DEFAULT 0")
            )

        if "max_choices" not in menu_columns:
            connection.execute(
                text("ALTER TABLE menu_category ADD COLUMN max_choices INTEGER")
            )

        if "required" not in menu_columns:
            connection.execute(
                text("ALTER TABLE menu_category ADD COLUMN required BOOLEAN NOT NULL DEFAULT 0")
            )

        if "selection_help" not in menu_columns:
            connection.execute(
                text("ALTER TABLE menu_category ADD COLUMN selection_help VARCHAR(240)")
            )
def ensure_database() -> None:
    INSTANCE_DIR.mkdir(parents=True, exist_ok=True)
    UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
    db.create_all()
    ensure_schema_updates()
    seed_content()


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


@app.after_request
def add_security_headers(response):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    return response


@app.errorhandler(413)
def upload_too_large(_error):
    flash(f"A imagem ultrapassa o limite de {MAX_UPLOAD_MB} MB.", "error")
    return redirect(request.referrer or url_for("admin_gallery"))


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
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


def month_from_query() -> tuple[int, int]:
    raw = request.args.get("mes")
    if raw:
        try:
            parsed = datetime.strptime(raw, "%Y-%m")
            return parsed.year, parsed.month
        except ValueError:
            pass
    today = date.today()
    return today.year, today.month


def add_months(year: int, month: int, delta: int) -> tuple[int, int]:
    zero_based = year * 12 + (month - 1) + delta
    return zero_based // 12, zero_based % 12 + 1


def active_event_count(day: date, exclude_event_id: int | None = None) -> int:
    query = Event.query.filter(Event.event_date == day, Event.status.in_(ACTIVE_STATUSES))
    if exclude_event_id is not None:
        query = query.filter(Event.id != exclude_event_id)
    return query.count()


def availability(day: date) -> dict:
    max_events = settings().max_events_per_day
    blocked = BlockedDate.query.filter_by(blocked_date=day).first()
    count = active_event_count(day)
    remaining = max(max_events - count, 0)

    if day < date.today():
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

    try:
        image = Image.open(file_storage.stream)
        image.verify()
        file_storage.stream.seek(0)
        image = Image.open(file_storage.stream)
        image = ImageOps.exif_transpose(image)
        if image.mode not in ("RGB", "RGBA"):
            image = image.convert("RGBA" if "transparency" in image.info else "RGB")
        image.thumbnail((2200, 2200), Image.Resampling.LANCZOS)
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError("O arquivo enviado não é uma imagem válida.") from exc

    filename = f"{prefix}-{uuid.uuid4().hex}.webp"
    target = UPLOAD_ROOT / filename
    target.parent.mkdir(parents=True, exist_ok=True)
    image.save(target, "WEBP", quality=88, method=6)
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
    return {"site": site_content(), "corporate": corporate_section()}


@app.get("/health")
def health():
    try:
        db.session.execute(text("SELECT 1"))
        return jsonify({"status": "ok"}), 200
    except Exception:
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
        return jsonify({"error": "Data inválida."}), 400
    return jsonify(availability(day))


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        supplied = request.form.get("password", "")
        expected = os.getenv("ADMIN_PASSWORD")
        if not expected:
            if os.getenv("RENDER") == "true":
                flash("A senha administrativa ainda não foi configurada na hospedagem.", "error")
                return render_template("admin/login.html", **admin_template_context()), 503
            expected = "troque-esta-senha"
        if secrets.compare_digest(supplied, expected):
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
    today = date.today()
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
            if BlockedDate.query.filter_by(blocked_date=event_date).first():
                flash("Esta data está bloqueada. Desbloqueie-a antes de cadastrar o evento.", "error")
                return redirect(url_for("admin_dashboard", mes=event_date.strftime("%Y-%m")))
            if active_event_count(event_date) >= settings().max_events_per_day:
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
                blocked = BlockedDate.query.filter_by(blocked_date=new_date).first()
                if blocked and new_date != event.event_date:
                    flash("A nova data está bloqueada.", "error")
                    return redirect(url_for("admin_edit_event", event_id=event.id))
                if active_event_count(new_date, exclude_event_id=event.id) >= settings().max_events_per_day:
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

    site.since_year = max(1900, min(date.today().year, safe_int(request.form.get("since_year"), site.since_year)))

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
        if site.logo_storage == "upload":
            remove_upload(site.logo_filename)
        site.logo_storage = "upload"
        site.logo_filename = filename
        db.session.commit()
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
        if site.official_menu_storage == "upload":
            remove_upload(site.official_menu_filename)
        site.official_menu_storage = "upload"
        site.official_menu_filename = filename
        db.session.commit()
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
    return render_template("admin/menu.html", categories=categories, active_page="cardapio", **admin_template_context())


@app.post("/admin/cardapio/categorias/nova")
@admin_required
def admin_new_category():
    name = request.form.get("name", "").strip()
    min_choices = max(
    0,
    safe_int(request.form.get("min_choices"), 0),
)

max_choices = max(
    0,
    safe_int(request.form.get("max_choices"), 0),
)
    
if not name:
    flash("Informe o nome da categoria.", "error")
elif max_choices > 0 and min_choices > max_choices:
    flash(
        "A quantidade mínima não pode ser maior que a quantidade máxima.",
        "error",
    )
else:
category = MenuCategory(
    name=name,
    description=request.form.get("description", "").strip() or None,
    selection_help=request.form.get("selection_help", "").strip() or None,
    min_choices=max(
        0,
        safe_int(request.form.get("min_choices"), 0),
    ),
    max_choices=max(
        0,
        safe_int(request.form.get("max_choices"), 0),
    ),
    active=request.form.get("active") == "on",
    sort_order=safe_int(request.form.get("sort_order"), 0),
)
        db.session.add(category)
        db.session.commit()
        flash("Categoria adicionada.", "success")
    return redirect(url_for("admin_menu"))


@app.post("/admin/cardapio/categorias/<int:category_id>/salvar")
@admin_required
def admin_save_category(category_id: int):
    category = MenuCategory.query.get_or_404(category_id)

    name = request.form.get("name", "").strip()

    if not name:
        flash("Informe o nome da categoria.", "error")
    else:
        min_choices = max(
            0,
            safe_int(request.form.get("min_choices"), 0),
        )

        max_choices = max(
            0,
            safe_int(request.form.get("max_choices"), 0),
        )

        if max_choices > 0 and min_choices > max_choices:
            flash(
                "A quantidade mínima não pode ser maior que a quantidade máxima.",
                "error",
            )
        else:
            category.name = name
            category.description = (
                request.form.get("description", "").strip() or None
            )
            category.selection_help = (
                request.form.get("selection_help", "").strip() or None
            )
            category.min_choices = min_choices
            category.max_choices = max_choices
            category.active = request.form.get("active") == "on"
            category.sort_order = safe_int(
                request.form.get("sort_order"),
                0,
            )

            db.session.commit()

            flash("Categoria atualizada.", "success")

    return redirect(
        url_for("admin_menu") + f"#categoria-{category_id}"
    )


@app.post("/admin/cardapio/categorias/<int:category_id>/excluir")
@admin_required
def admin_delete_category(category_id: int):
    category = MenuCategory.query.get_or_404(category_id)
    db.session.delete(category)
    db.session.commit()
    flash("Categoria e seus itens foram excluídos.", "success")
    return redirect(url_for("admin_menu"))


@app.post("/admin/cardapio/itens/novo")
@admin_required
def admin_new_menu_item():
    category_id = safe_int(request.form.get("category_id"))
    category = MenuCategory.query.get_or_404(category_id)
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
    next_order = (db.session.query(db.func.max(GalleryImage.sort_order)).scalar() or 0) + 1
    for file_storage in files:
        try:
            filename = save_uploaded_image(file_storage, prefix="galeria")
            db.session.add(GalleryImage(storage="upload", filename=filename, category=category, active=True, sort_order=next_order))
            next_order += 1
            added += 1
        except ValueError as exc:
            errors.append(f"{file_storage.filename}: {exc}")
    db.session.commit()
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
    if image.storage == "upload":
        remove_upload(image.filename)
    db.session.delete(image)
    db.session.commit()
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
    db.session.commit()
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
    if file_storage and file_storage.filename:
        try:
            new_filename = save_uploaded_image(file_storage, prefix="equipe")
            if member.image_storage == "upload":
                remove_upload(member.image_filename)
            member.image_storage = "upload"
            member.image_filename = new_filename
        except ValueError as exc:
            flash(str(exc), "error")
            return redirect(url_for("admin_team") + f"#integrante-{member.id}")

    db.session.commit()
    flash("Integrante atualizado.", "success")
    return redirect(url_for("admin_team") + f"#integrante-{member.id}")


@app.post("/admin/equipe/<int:member_id>/excluir")
@admin_required
def admin_delete_team_member(member_id: int):
    member = TeamMember.query.get_or_404(member_id)
    if member.image_storage == "upload":
        remove_upload(member.image_filename)
    db.session.delete(member)
    db.session.commit()
    flash("Integrante excluído.", "success")
    return redirect(url_for("admin_team"))


@app.context_processor
def inject_globals():
    site = site_content()
    return {
        "current_year": datetime.now().year,
        "csrf_token": get_csrf_token,
        "image_url": image_url,
        "gallery_image_url": gallery_image_url,
        "money_br": lambda value: f"{Decimal(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
    }


if __name__ == "__main__":
    app.run(debug=os.getenv("FLASK_DEBUG") == "1", host="0.0.0.0", port=int(os.getenv("PORT", "5000")))
