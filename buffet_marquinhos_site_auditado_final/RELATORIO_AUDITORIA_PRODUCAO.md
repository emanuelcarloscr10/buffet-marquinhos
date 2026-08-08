# Relatório de auditoria — Buffet do Marquinhos

Data da revisão: 08/08/2026

## Objetivo

Preparar o site para uso empresarial no Render com persistência de dados, fluxo de orçamento por WhatsApp em celular e desktop, regras de cardápio coerentes com a operação do buffet e proteções básicas do painel administrativo.

## Persistência e banco de dados

- Produção preparada para PostgreSQL por `DATABASE_URL`.
- O painel bloqueia gravações de negócio no Render enquanto um PostgreSQL persistente não estiver conectado, evitando novos cadastros em SQLite efêmero.
- Agenda, bloqueios de data, textos, preços, pacotes, cardápio, regras e equipe ficam no banco.
- Imagens enviadas pelo painel usam `UPLOAD_ROOT`; em produção o projeto está preparado para `/var/data/uploads` em Persistent Disk.
- Dados padrão são inseridos somente na primeira inicialização do banco; exclusões e edições administrativas não são recriadas a cada restart.
- Atualizações de esquema são aditivas para a estrutura atual.
- `/health` testa a conexão com o banco e informa o tipo de armazenamento.

## Agenda

- Limite de eventos por dia permanece configurável.
- Eventos cancelados não ocupam capacidade.
- Datas passadas usam o fuso comercial `America/Sao_Paulo`.
- No PostgreSQL, a verificação de capacidade usa bloqueio transacional (`FOR UPDATE`) para reduzir risco de duas gravações concorrentes ultrapassarem o limite.
- Botões administrativos são desabilitados imediatamente no envio para reduzir cadastros duplicados por duplo clique.

## Cardápio

Comportamento configurado:

- Entrada: determinada pelo pacote (com ou sem entrada); a seção é informativa, sem seleção prato por prato.
- Massas: escolha única, exatamente 1 opção.
- Strogonoff: escolha única, Carne ou Frango.
- Lasanha: escolha única de 1 sabor.
- Sobremesas: escolha múltipla, até 3 opções por bloco iniciado de 100 convidados, somente em pacotes com sobremesa.
- Churrasco: informativo, sem seleção; variedades padrão do buffet.
- Saladas: informativo, sem seleção; oito variedades, incluindo folhas, legumes e vinagrete.
- Incluso: informativo, sem seleção; o cliente não precisa marcar o que já acompanha o serviço.
- Não existe mais ação global de “selecionar tudo”.
- O painel permite definir se uma categoria é informativa, escolha única ou múltipla e quando ela aparece (sempre, com entrada ou com sobremesa).

## WhatsApp e celular

- O envio final usa `https://wa.me/`.
- Não há `fetch`/`await` entre o toque em “Enviar pelo WhatsApp” e a navegação final, evitando perda do gesto do usuário em navegadores móveis.
- A disponibilidade é consultada anteriormente, ao selecionar a data.
- Existe link alternativo caso a abertura automática do WhatsApp falhe.
- A mensagem inclui dados do evento, pacote, escolhas do cardápio, observações e informação de disponibilidade.

## Painel administrativo e segurança

- Rotas administrativas protegidas por autenticação, exceto login.
- CSRF em formulários POST administrativos.
- Sessão regenerada após login.
- Cookies de sessão `HttpOnly`, `SameSite=Lax` e `Secure` no Render.
- Cabeçalhos de segurança, incluindo CSP, HSTS no Render, `X-Frame-Options`, `X-Content-Type-Options` e política de permissões.
- Senha administrativa e `SECRET_KEY` vêm de variáveis de ambiente; não ficam hardcoded no projeto.
- Erros de banco fazem rollback e geram resposta amigável no painel.
- Uploads de imagem validam extensão, conteúdo, dimensões e tamanho e usam nomes UUID.
- Substituição de imagem preserva o arquivo anterior se o commit do banco falhar.

## Verificações executadas nesta revisão

- `python -m py_compile app.py`: aprovado.
- `node --check static/js/main.js`: aprovado.
- `node --check static/js/admin.js`: aprovado.
- `python tests/qa_static.py`: **Auditoria estática aprovada**.
- 44 imagens do pacote foram abertas/verificadas com Pillow sem corrupção.
- Auditoria estática inclui rotas, endpoints, autenticação administrativa, CSRF, sintaxe Jinja, IDs/âncoras, referências de imagens, configuração Render, regras de cardápio, persistência, WhatsApp e proteções contra regressões já encontradas.

## Limite da auditoria antes da publicação

A revisão local consegue validar código, templates, JavaScript, assets e configuração, mas não substitui o teste de integração no ambiente real do Render. O PostgreSQL, o Persistent Disk, o domínio, o Safari/iPhone e o aplicativo WhatsApp dependem do ambiente externo e devem ser confirmados após o deploy.

Por isso a publicação só deve ser considerada aceita depois dos testes abaixo.

## Teste de aceitação obrigatório após o deploy

1. Acessar `/health` e confirmar banco PostgreSQL/persistente.
2. Entrar no painel e cadastrar um evento fictício.
3. Atualizar a página e confirmar que o evento continua lá.
4. Fazer um novo deploy/restart e confirmar novamente o mesmo evento.
5. Editar e excluir o evento fictício.
6. Alterar temporariamente um item do cardápio, atualizar/reiniciar e confirmar persistência.
7. Enviar uma imagem de teste pelo painel e confirmar que ela continua disponível depois de novo deploy/restart.
8. No celular real, montar um orçamento e tocar em “Enviar pelo WhatsApp”; confirmar abertura do WhatsApp com a mensagem pronta.
9. Repetir o orçamento no computador.
10. Testar pacotes com/sem entrada e com/sem sobremesa.
11. Confirmar: massa = 1, strogonoff = 1, lasanha = 1, sobremesa = limite dinâmico, churrasco/saladas/incluso = sem seleção.
12. Só depois recadastrar a agenda real.

## Atenção sobre os eventos perdidos

O ZIP recebido não contém o arquivo do banco SQLite que rodava temporariamente no Render. Portanto, os eventos que já desapareceram não podem ser recuperados deste ZIP. O novo PostgreSQL evita que os próximos cadastros dependam desse arquivo efêmero.
