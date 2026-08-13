"""Quality gates estáticos e sem dependências para o portfólio."""

from __future__ import annotations

import json
import re
import struct
import sys
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "index.html"
PRODUCTION_URL = "https://luanaabastos.github.io/portfolio/"
VOID_ELEMENTS = {
    "area",
    "base",
    "br",
    "col",
    "embed",
    "hr",
    "img",
    "input",
    "link",
    "meta",
    "param",
    "source",
    "track",
    "wbr",
}
REFERENCE_ATTRIBUTES = ("aria-controls", "aria-describedby", "aria-labelledby")


class PortfolioParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.errors: list[str] = []
        self.stack: list[str] = []
        self.elements: list[tuple[str, dict[str, str]]] = []
        self.ids: dict[str, str] = {}
        self.duplicate_ids: set[str] = set()
        self.json_ld: list[str] = []
        self._json_chunks: list[str] | None = None
        self._in_title = False
        self.title_chunks: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = {name: value or "" for name, value in attrs}
        self.elements.append((tag, attributes))

        element_id = attributes.get("id")
        if element_id:
            if element_id in self.ids:
                self.duplicate_ids.add(element_id)
            self.ids[element_id] = tag

        if tag == "title":
            self._in_title = True
        if tag == "script" and attributes.get("type") == "application/ld+json":
            self._json_chunks = []
        if tag not in VOID_ELEMENTS:
            self.stack.append(tag)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        if tag not in VOID_ELEMENTS:
            self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False
        if tag == "script" and self._json_chunks is not None:
            self.json_ld.append("".join(self._json_chunks).strip())
            self._json_chunks = None

        if not self.stack:
            self.errors.append(f"fechamento </{tag}> sem abertura")
            return
        if self.stack[-1] != tag:
            self.errors.append(
                f"fechamento </{tag}> encontrado com <{self.stack[-1]}> ainda aberto"
            )
            if tag in self.stack:
                while self.stack and self.stack[-1] != tag:
                    self.stack.pop()
                self.stack.pop()
            return
        self.stack.pop()

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title_chunks.append(data)
        if self._json_chunks is not None:
            self._json_chunks.append(data)


def fail(errors: list[str], message: str) -> None:
    errors.append(message)


def local_path(raw_url: str) -> Path | None:
    if not raw_url or raw_url.startswith(("#", "mailto:", "tel:", "data:")):
        return None
    parts = urlsplit(raw_url)
    if parts.scheme or parts.netloc:
        return None
    relative = unquote(parts.path).lstrip("/")
    if not relative:
        return INDEX
    return ROOT / relative


def png_dimensions(path: Path) -> tuple[int, int] | None:
    data = path.read_bytes()[:24]
    if len(data) != 24 or data[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    return struct.unpack(">II", data[16:24])


def main() -> int:
    errors: list[str] = []
    html = INDEX.read_text(encoding="utf-8")
    parser = PortfolioParser()
    parser.feed(html)
    parser.close()

    if parser.stack:
        fail(errors, f"elementos sem fechamento: {', '.join(parser.stack)}")
    errors.extend(parser.errors)
    if parser.duplicate_ids:
        fail(errors, f"IDs duplicados: {', '.join(sorted(parser.duplicate_ids))}")

    elements = parser.elements
    by_tag: dict[str, list[dict[str, str]]] = {}
    for tag, attrs in elements:
        by_tag.setdefault(tag, []).append(attrs)

    html_elements = by_tag.get("html", [])
    if len(html_elements) != 1 or html_elements[0].get("lang") != "pt-BR":
        fail(errors, "<html> deve declarar lang=\"pt-BR\"")
    if len(by_tag.get("main", [])) != 1:
        fail(errors, "a página deve ter exatamente um <main>")
    if len(by_tag.get("h1", [])) != 1:
        fail(errors, "a página deve ter exatamente um <h1>")

    title = " ".join("".join(parser.title_chunks).split())
    if not 20 <= len(title) <= 60:
        fail(errors, f"title deve ter entre 20 e 60 caracteres; atual: {len(title)}")

    meta_by_name = {
        attrs.get("name", "").lower(): attrs.get("content", "").strip()
        for attrs in by_tag.get("meta", [])
        if attrs.get("name")
    }
    meta_by_property = {
        attrs.get("property", "").lower(): attrs.get("content", "").strip()
        for attrs in by_tag.get("meta", [])
        if attrs.get("property")
    }

    description = meta_by_name.get("description", "")
    if not 70 <= len(description) <= 160:
        fail(errors, f"meta description deve ter entre 70 e 160 caracteres; atual: {len(description)}")
    if meta_by_name.get("robots") != "index, follow":
        fail(errors, "meta robots deve ser 'index, follow'")
    if "keywords" in meta_by_name:
        fail(errors, "meta keywords não deve ser usada")

    required_open_graph = {
        "og:type",
        "og:locale",
        "og:title",
        "og:description",
        "og:url",
        "og:image",
        "og:image:width",
        "og:image:height",
        "og:image:alt",
    }
    missing_og = sorted(key for key in required_open_graph if not meta_by_property.get(key))
    if missing_og:
        fail(errors, f"Open Graph incompleto: {', '.join(missing_og)}")

    required_twitter = {
        "twitter:card",
        "twitter:title",
        "twitter:description",
        "twitter:image",
        "twitter:image:alt",
    }
    missing_twitter = sorted(key for key in required_twitter if not meta_by_name.get(key))
    if missing_twitter:
        fail(errors, f"Twitter Card incompleto: {', '.join(missing_twitter)}")

    links = by_tag.get("link", [])
    canonical = next(
        (attrs.get("href") for attrs in links if "canonical" in attrs.get("rel", "").split()),
        None,
    )
    if canonical != PRODUCTION_URL:
        fail(errors, f"canonical deve apontar para {PRODUCTION_URL}")

    icon_rels = {token for attrs in links for token in attrs.get("rel", "").split()}
    if "icon" not in icon_rels or "apple-touch-icon" not in icon_rels:
        fail(errors, "favicon e Apple Touch Icon devem estar declarados")

    if len(parser.json_ld) != 1:
        fail(errors, "deve existir exatamente um bloco JSON-LD")
    else:
        try:
            person = json.loads(parser.json_ld[0])
        except json.JSONDecodeError as exc:
            fail(errors, f"JSON-LD inválido: {exc}")
        else:
            if person.get("@type") != "Person":
                fail(errors, "JSON-LD deve descrever uma Person")
            for key in ("name", "url", "jobTitle", "sameAs", "knowsAbout"):
                if not person.get(key):
                    fail(errors, f"JSON-LD sem {key}")
            if any(key in person for key in ("worksFor", "alumniOf", "award")):
                fail(errors, "JSON-LD contém vínculo ou credencial fora do escopo confirmado")

    labels = {attrs.get("for") for attrs in by_tag.get("label", []) if attrs.get("for")}
    for tag in ("input", "textarea", "select"):
        for attrs in by_tag.get(tag, []):
            if tag == "input" and attrs.get("type", "text") in {"hidden", "button", "submit"}:
                continue
            field_id = attrs.get("id")
            if not field_id:
                fail(errors, f"<{tag}> sem id")
            elif field_id not in labels and not (attrs.get("aria-label") or attrs.get("aria-labelledby")):
                fail(errors, f"campo #{field_id} sem label acessível")

    for attrs in by_tag.get("button", []):
        if not attrs.get("type"):
            fail(errors, "todo <button> deve declarar type")

    for tag, attrs in elements:
        for reference_attribute in REFERENCE_ATTRIBUTES:
            for referenced_id in attrs.get(reference_attribute, "").split():
                if referenced_id and referenced_id not in parser.ids:
                    fail(errors, f"{reference_attribute} referencia ID ausente: {referenced_id}")

    for attrs in by_tag.get("a", []):
        href = attrs.get("href", "")
        if href.startswith("#") and href[1:] not in parser.ids:
            fail(errors, f"âncora interna inexistente: {href}")
        if attrs.get("target") == "_blank":
            rel = set(attrs.get("rel", "").split())
            if not {"noopener", "noreferrer"}.issubset(rel):
                fail(errors, f"link externo sem noopener noreferrer: {href}")

    referenced_local_files: set[Path] = set()
    for tag, attrs in elements:
        for attribute in ("href", "src"):
            path = local_path(attrs.get(attribute, ""))
            if path is not None:
                referenced_local_files.add(path)
                if not path.exists():
                    fail(errors, f"ativo ou página local ausente: {path.relative_to(ROOT)}")

    for attrs in by_tag.get("img", []):
        src = attrs.get("src", "")
        if not attrs.get("alt"):
            fail(errors, f"imagem sem alt: {src}")
        if not (attrs.get("width", "").isdigit() and attrs.get("height", "").isdigit()):
            fail(errors, f"imagem sem dimensões numéricas: {src}")
        if attrs.get("decoding") != "async":
            fail(errors, f"imagem sem decoding=async: {src}")
        if "profile" in src:
            if attrs.get("loading") != "eager" or attrs.get("fetchpriority") != "high":
                fail(errors, "foto do Hero deve usar loading=eager e fetchpriority=high")
        elif attrs.get("loading") != "lazy":
            fail(errors, f"imagem abaixo da dobra sem loading=lazy: {src}")

    social_image = meta_by_property.get("og:image", "")
    if social_image.startswith(PRODUCTION_URL):
        social_path = ROOT / unquote(social_image.removeprefix(PRODUCTION_URL))
        if not social_path.exists():
            fail(errors, "imagem social declarada não existe")
        elif png_dimensions(social_path) != (1200, 630):
            fail(errors, "imagem social deve ter 1200x630")

    required_files = (
        ROOT / "favicon.ico",
        ROOT / "robots.txt",
        ROOT / "sitemap.xml",
        ROOT / "assets/icons/favicon.svg",
        ROOT / "assets/icons/favicon-32.png",
        ROOT / "assets/icons/apple-touch-icon.png",
        ROOT / "_archive/redessociais/README.md",
        ROOT / "_archive/redessociais/redessociais.html",
        ROOT / "_archive/redessociais/assets/css/stylesociais.css",
        ROOT / "_archive/redessociais/assets/js/svg-inject.min.js",
        ROOT / "_archive/redessociais/icons8-programação-96.png",
    )
    for path in required_files:
        if not path.exists() or path.stat().st_size == 0:
            fail(errors, f"arquivo obrigatório ausente ou vazio: {path.relative_to(ROOT)}")

    if (ROOT / "redessociais.html").exists():
        fail(errors, "redessociais.html legado não deve permanecer na raiz publicável")

    robots = (ROOT / "robots.txt").read_text(encoding="utf-8")
    if f"Sitemap: {PRODUCTION_URL}sitemap.xml" not in robots:
        fail(errors, "robots.txt não aponta para o sitemap de produção")
    try:
        sitemap = ET.parse(ROOT / "sitemap.xml")
        namespace = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        locations = [node.text for node in sitemap.findall(".//sm:loc", namespace)]
        if locations != [PRODUCTION_URL]:
            fail(errors, "sitemap deve conter apenas a URL canônica confirmada")
    except ET.ParseError as exc:
        fail(errors, f"sitemap.xml inválido: {exc}")

    css_path = ROOT / "assets/css/style.css"
    css = css_path.read_text(encoding="utf-8")
    css_without_comments = re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)
    if css_without_comments.count("{") != css_without_comments.count("}"):
        fail(errors, "CSS tem chaves desbalanceadas")

    size_limits = {
        INDEX: 80_000,
        css_path: 50_000,
        ROOT / "assets/images/profile-avatar.webp": 100_000,
        ROOT / "assets/images/social/luana-bastos-quality-engineering.png": 700_000,
    }
    for path, maximum in size_limits.items():
        if path.stat().st_size > maximum:
            fail(errors, f"{path.relative_to(ROOT)} excede {maximum:,} bytes")

    if errors:
        print("QUALITY GATES: FALHA")
        for error in errors:
            print(f"- {error}")
        return 1

    print("QUALITY GATES: OK")
    print(f"- {len(elements)} elementos HTML analisados")
    print(f"- {len(parser.ids)} IDs únicos e referências ARIA verificadas")
    print(f"- {len(referenced_local_files)} arquivos locais referenciados e presentes")
    print(f"- {len(by_tag.get('img', []))} imagens com alt, dimensões e estratégia de carregamento")
    print("- SEO, Open Graph, Twitter Card, JSON-LD, robots e sitemap válidos")
    return 0


if __name__ == "__main__":
    sys.exit(main())
