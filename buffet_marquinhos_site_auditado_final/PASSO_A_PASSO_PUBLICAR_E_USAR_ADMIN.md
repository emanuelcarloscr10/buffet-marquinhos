# Buffet do Marquinhos — publicação e uso do painel

## Antes de usar o painel com dados reais

Siga `MIGRACAO_RENDER_PRODUCAO.md`. A Agenda deve mostrar:

**Banco: PostgreSQL · Persistente**

Se aparecer **Modo de proteção**, não cadastre eventos. O bloqueio existe para impedir dados temporários no SQLite do Render.

## Agenda

No painel você pode cadastrar, editar, cancelar/excluir eventos, bloquear datas e alterar a capacidade diária.

- `Reservado` e `Confirmado` ocupam vaga.
- `Cancelado` não ocupa vaga.
- O site público mostra somente disponibilidade, sem revelar nome/telefone do cliente.
- O fuso utilizado é `America/Sao_Paulo`.
- Após a primeira migração, faça um evento fictício, um novo deploy e confirme que ele continua salvo.

## Textos e preços

Em **Textos e preços**, você controla textos públicos, contatos e pacotes.

Cada pacote possui duas marcações importantes:

- **Inclui entrada**;
- **Inclui sobremesa**.

Essas marcações controlam automaticamente o que o cliente vê no montador do orçamento.

## Cardápio

Cada categoria tem um **Tipo**:

- **Somente informativa**: mostra itens sem seleção. Use para Churrasco, Saladas, Incluso, Entrada e demais itens fixos.
- **Escolha única**: exige exatamente uma opção. Use para Massas, Strogonoff e Lasanha.
- **Múltipla escolha**: permite várias opções com limites. Para Sobremesas, use `3` em **Opções a cada 100 convidados**.

Também existe **Quando aparece**:

- Sempre mostrar;
- Somente em pacotes com entrada;
- Somente em pacotes com sobremesa.

Configuração recomendada:

- Entradas: Informativa + Somente em pacotes com entrada;
- Massas: Escolha única;
- Strogonoff: Escolha única;
- Lasanha: Escolha única;
- Churrasco: Informativa;
- Saladas: Informativa;
- Sobremesas: Múltipla + 3 por 100 + Somente em pacotes com sobremesa;
- Incluso: Informativa.

## Fotos

Uploads do painel ficam em `UPLOAD_ROOT`. Em produção:

`UPLOAD_ROOT=/var/data/uploads`

O Web Service precisa ter Persistent Disk montado em `/var/data`. Não remova esse disco enquanto houver arquivos enviados pelo painel.

## WhatsApp

O formulário público usa o número salvo no painel. No envio final, o site abre `https://wa.me/...` diretamente, sem consulta assíncrona no meio do toque. Existe um link alternativo caso o aplicativo não abra automaticamente.

Teste sempre em:

- iPhone/Safari ou navegador padrão do iPhone;
- Android/Chrome (se disponível);
- computador.

## Atualizações futuras

Com PostgreSQL + Persistent Disk configurados, o fluxo normal volta a ser:

```bash
git add .
git commit -m "Descrição da alteração"
git push
```

Novo deploy troca o código, mas não deve apagar agenda/cardápio/textos do PostgreSQL nem arquivos guardados no disco persistente.

Antes de alterações importantes em produção, gere uma exportação/backup do Postgres no Render.
