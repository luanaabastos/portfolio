# Portfólio de Quality Engineering

Portfólio profissional de Luana do Amaral Bastos, direcionado a posições de
Senior QA Automation Engineer, Senior Software Test Engineer, Senior QA Engineer
e Quality Engineer. O projeto prioriza evidências verificáveis, contexto de uso
das tecnologias e limites explícitos para projetos ainda em desenvolvimento.

Produção: <https://luanaabastos.github.io/portfolio/>

## Arquitetura

Site estático de página única, sem framework ou etapa de build:

- `index.html`: conteúdo semântico, metadados e comportamento em JavaScript;
- `assets/css/style.css`: layout, temas e breakpoints responsivos;
- `assets/images`: foto, evidências e imagem social otimizadas;
- `assets/icons`: favicon e Apple Touch Icon;
- `tests/portfolio_quality.py`: gates estáticos sem dependências externas;
- `.github/workflows/portfolio-quality.yml`: execução automatizada dos gates.

## Decisões de qualidade

- Conteúdo profissional separado entre experiência, Engineering Case, estudo e
  contexto ainda não confirmado.
- Case principal sustentado por repositório, release, workflow e relatório de
  execução públicos.
- Imagens abaixo da dobra usam carregamento tardio; a foto do Hero é priorizada.
- Imagens têm formato otimizado, dimensões explícitas e texto alternativo.
- CSS e JavaScript permanecem legíveis e sem pipeline de minificação para reduzir
  complexidade operacional neste projeto estático.

## Acessibilidade

Foram implementados skip link, landmarks, hierarquia de headings, foco visível,
menu operável por teclado, retorno de foco com `Escape`, respeito a
`prefers-reduced-motion` e feedback acessível do formulário com `aria-invalid`,
`aria-describedby` e região de status.

Essas verificações não constituem declaração de conformidade WCAG completa.

## SEO e compartilhamento

O projeto inclui canonical, robots, sitemap, Open Graph, Twitter Card, imagem
social 1200 × 630, favicon e JSON-LD `Person`. Todas as URLs públicas apontam
para a URL de produção confirmada.

## Execução local

Requer Python 3:

```bash
python -m http.server 8000
```

Acesse <http://127.0.0.1:8000/>.

## Validação

Execute os gates locais:

```bash
python tests/portfolio_quality.py
```

O script verifica estrutura HTML, IDs, referências ARIA, labels, links internos,
assets, estratégia de imagens, metadados SEO, JSON-LD, robots, sitemap, CSS e
limites de peso. O mesmo comando é executado pelo workflow de qualidade.

Lighthouse pode ser executado temporariamente, sem adicionar dependências ao
projeto, contra o servidor local:

```bash
npx --yes lighthouse@12.8.2 http://127.0.0.1:8000/ --only-categories=performance,accessibility,best-practices,seo
```

## Limitações conhecidas

- O envio real do Formspree exige autorização e não faz parte dos testes locais.
- Previews de LinkedIn, Open Graph e Twitter precisam ser validados após a
  publicação dos novos assets.
- O Lighthouse local usa um servidor Python sem compressão ou cache de produção;
  esses diagnósticos devem ser interpretados separadamente do código do site.
- A página profissional antiga foi preservada em `_archive/redessociais/`. O
  diretório iniciado por `_` fica fora da publicação Jekyll padrão; outro pipeline
  de hospedagem deve excluí-lo explicitamente.
