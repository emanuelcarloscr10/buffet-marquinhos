# Buffet do Marquinhos — versão revisada para produção

Site Flask com painel administrativo, agenda, cardápio, preços, galeria, equipe e orçamento por WhatsApp.

## Arquitetura de produção

A versão revisada separa código, dados e arquivos:

- **Render Web Service pago**: Flask/Gunicorn;
- **Render Postgres**: agenda, bloqueios, textos, preços, pacotes, cardápio, regras e equipe;
- **Persistent Disk `/var/data`**: fotos, logo e cardápio oficial enviados pelo painel;
- **GitHub**: código-fonte e imagens estáticas do projeto.

No Render, se o app ainda estiver usando SQLite, o painel entra em **modo de proteção** e bloqueia gravações. Isso evita repetir a perda de dados causada pelo filesystem efêmero.

Leia `MIGRACAO_RENDER_PRODUCAO.md` antes do primeiro deploy desta versão.

## Regras do cardápio

- **Pacotes** determinam se o orçamento é com/sem entrada e com/sem sobremesa.
- **Entrada**: informativa, sem escolha prato por prato.
- **Massas**: exatamente 1 opção.
- **Strogonoff**: exatamente 1 (Carne ou Frango).
- **Lasanha**: exatamente 1 sabor.
- **Sobremesas**: até 3 opções por bloco iniciado de 100 convidados.
- **Churrasco**: informativo, sem checkbox.
- **Saladas**: informativo; oito variedades, incluindo folhas, legumes e vinagrete.
- **Incluso**: informativo, sem checkbox.

No painel `/admin/cardapio`, cada categoria possui:

- Tipo: informativa / escolha única / múltipla escolha;
- Quando aparece: sempre / pacote com entrada / pacote com sobremesa;
- orientação para o cliente;
- mínimo, máximo e limite por 100 convidados;
- ordem e visibilidade.

## WhatsApp

O envio final do orçamento usa `wa.me` e não faz `fetch`/`await` entre o toque do cliente e a navegação. A consulta de disponibilidade ocorre antes, quando a data é selecionada. Existe um link alternativo caso o navegador não abra o WhatsApp automaticamente.

## Agenda

- capacidade diária configurável;
- status Reservado/Confirmado contam vaga; Cancelado não;
- bloqueio/desbloqueio de datas;
- edição e exclusão;
- API pública sem cache;
- fuso `America/Sao_Paulo` para evitar divergência de data com o servidor;
- validação transacional de capacidade no PostgreSQL;
- proteção de duplo envio no painel.

## Segurança e uploads

- autenticação administrativa;
- `SECRET_KEY` e `ADMIN_PASSWORD` exigidas em produção;
- CSRF em POST administrativo;
- cookies seguros;
- painel com `no-store`;
- HSTS e Content-Security-Policy;
- rollback em falhas de banco;
- upload JPG/PNG/WEBP, limite de 12 MB e até 40 megapixels;
- conversão para WEBP e nomes aleatórios;
- arquivos trocados/excluídos somente após commit seguro no banco.

## Saúde

`GET /health` testa a conexão com o banco e informa:

- status;
- tipo do banco;
- persistência;
- fuso do negócio.

## Desenvolvimento local

SQLite continua permitido apenas para desenvolvimento local.

1. Python 3.12+
2. ambiente virtual
3. `pip install -r requirements.txt`
4. configure `.env`/variáveis com base em `.env.example`
5. `python app.py`
6. abra `http://127.0.0.1:5000`

## Auditoria incluída

```bash
python -m py_compile app.py
python tests/qa_static.py
node --check static/js/main.js
node --check static/js/admin.js
```

A auditoria verifica sintaxe, templates, imagens, rotas, autenticação, CSRF, endpoints, IDs/âncoras, Render/Postgres/disco, regras do cardápio, fluxo móvel do WhatsApp, uploads e proteções contra regressões conhecidas.

## Observação importante

O PostgreSQL novo não recupera automaticamente os eventos que já desapareceram do antigo SQLite efêmero. Não recadastre a agenda real até confirmar no painel **Banco: PostgreSQL · Persistente** e concluir o teste de persistência do guia de migração.
