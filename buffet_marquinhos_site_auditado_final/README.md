# Buffet do Marquinhos — site com painel administrativo

Site em Python/Flask com agenda, banco de dados e painel para editar o conteúdo sem mexer no código.

## O que pode ser alterado em `/admin`

- Agenda: cadastrar, editar, cancelar e excluir eventos; bloquear datas; mudar o limite diário.
- Textos e contatos: história, títulos, avisos, WhatsApp, Instagram, endereço e CNPJ.
- Preços: adicionar, editar, ocultar, ordenar e excluir pacotes.
- Cardápio: adicionar, editar, ocultar, ordenar e excluir categorias e opções.
- Fotos: enviar, excluir, ocultar, organizar por categoria e escolher capa/fotos da história.
- Logo e imagem do cardápio oficial.

As fotos públicas aparecem sem nomes ou legendas.

## Testar no Windows

1. Instale Python 3.12 ou mais recente.
2. Dê dois cliques em `INICIAR_SITE_WINDOWS.bat`.
3. Aguarde a instalação das bibliotecas.
4. Abra `http://127.0.0.1:5000`.
5. Painel: `http://127.0.0.1:5000/admin`.
6. Senha local inicial: `troque-esta-senha`.

Essa senha é apenas para teste. Na publicação, escolha uma senha forte no Render.

## Publicar no Render

O projeto contém `render.yaml`, preparado para:

- serviço web Python no plano Starter;
- banco SQLite e fotos em disco persistente de 1 GB;
- senha administrativa configurada como variável secreta.

Passos resumidos:

1. Crie um repositório no GitHub.
2. Envie **o conteúdo desta pasta**, não apenas o arquivo ZIP.
3. No Render, escolha `New` > `Blueprint`.
4. Conecte o repositório.
5. Quando solicitado, defina `ADMIN_PASSWORD` com uma senha forte.
6. Confirme a criação do serviço.
7. Depois do deploy, o Render fornecerá um endereço terminado em `.onrender.com`.
8. Acesse `/admin` nesse endereço.

## Dados permanentes

O `render.yaml` monta um disco em `/var/data`. O banco e as fotos enviadas pelo painel ficam nesse disco e não somem em reinicializações ou novos deploys.

Não altere estas variáveis no Render sem necessidade:

- `DATABASE_URL=sqlite:////var/data/buffet.db`
- `UPLOAD_ROOT=/var/data/uploads`

## Estrutura principal

- `app.py`: aplicação, banco de dados, agenda e painel.
- `templates/index.html`: site público.
- `templates/admin/`: telas administrativas.
- `static/css/style.css`: visual.
- `static/js/`: interações.
- `static/images/`: fotos iniciais e identidade visual.
- `render.yaml`: publicação automática no Render.



## Atualização visual da galeria

- Logo oficial em alta resolução fornecida pelo Buffet do Marquinhos.
- Galeria pública organizada nesta ordem:
  1. Churrasco
  2. Pratos
  3. Saladas
  4. Sobremesas
- As fotos permanecem sem nomes ou legendas genéricas.


## Ajuste recente

- Logo atualizada para versão com fundo removido (PNG transparente).


## Substituições de fotos

Foram alteradas somente estas quatro fotos da galeria:

- primeira foto de Churrasco;
- um prato quente em refratário, substituído pelo strogonoff;
- uma salada de cenoura, substituída pela salada de beterraba;
- primeira sobremesa de bombom, substituída pelo mousse de limão.

O layout, os textos, as cores e as demais imagens foram mantidos.


## Agenda lotada e WhatsApp

- Datas lotadas não bloqueiam mais o envio do pedido de orçamento.
- O cliente recebe uma mensagem formal explicando que poderá consultar uma alternativa ou possibilidade excepcional de atendimento.
- A mensagem enviada ao WhatsApp informa a situação da agenda.
- O botão flutuante usa agora o ícone vetorial correto do WhatsApp, em vez da letra “W”.


## Versão pronta para publicação

- Aviso: 3 opções de sobremesas a cada 100 convidados.
- Aviso editável pelo painel em Textos e preços.
- Painel administrativo completo em `/admin`.
- Guia detalhado disponível em `PASSO_A_PASSO_PUBLICAR_E_USAR_ADMIN.md`.


## Correção da versão para celular

- menu público com botões de toque maiores;
- navegação explícita até cada seção com compensação do cabeçalho fixo;
- correção específica para Safari/iPhone ao fechar o menu e navegar no mesmo toque;
- fechamento ao tocar fora, pressionar Escape ou mudar para tela grande;
- atributos de acessibilidade e indicação visual de menu aberto;
- menu administrativo móvel corrigido com a mesma lógica.


## Correção do orçamento por WhatsApp

O formulário passa a abrir a página oficial de envio do WhatsApp na mesma aba. Isso evita o bloqueio de pop-up causado pela consulta assíncrona da agenda antes da abertura do aplicativo.

## Seção Quem somos

- As fotografias de clientes, bancos e cooperativas foram removidas.
- A página agora apresenta Marquinhos, Virgínia e a equipe.
- O painel ganhou a área `/admin/equipe`.
- Nessa área é possível trocar fotos, nomes, funções, textos, visibilidade e ordem.


## Atualização das fotografias de pratos

As seis fotografias anteriores da seção **Pratos** foram retiradas da galeria pública e substituídas pelas seis novas imagens enviadas pelo Buffet do Marquinhos:

- arroz colorido;
- prato cremoso;
- arroz com carne;
- prato gratinado;
- aipim com bacon;
- mesa posta.

A alteração também é aplicada automaticamente caso o site já esteja publicado com o banco de dados da versão anterior. Fotografias personalizadas adicionadas pelo painel não são sobrescritas.


## Fotografias reais da equipe

A seção **Quem somos** foi atualizada com:

- fotografia real do Marquinhos;
- fotografia real da Virgínia, sem o prato nas mãos;
- fotografia coletiva da equipe;
- identificação da Virgínia como proprietária, fundadora e responsável pela cozinha;
- texto institucional sobre sua participação na preparação, organização e elaboração dos alimentos;
- exibição integral da fotografia coletiva, evitando o corte de integrantes.


## Atualização das fotografias e do cardápio personalizável

- A fotografia do Marquinhos foi substituída pela nova imagem dele trabalhando no buffet.
- A fotografia coletiva da equipe foi substituída pela nova imagem enviada.
- A foto coletiva é exibida inteira para evitar o corte de integrantes.
- A seção Cardápio agora informa que também são elaborados cardápios personalizados de acordo com o gosto do cliente.
- Podem ser solicitados pratos que não estejam no cardápio padrão, mediante consulta e orçamento.
- A atualização do texto também é aplicada a instalações já iniciadas, desde que o texto anterior não tenha sido personalizado no painel.


## Auditoria final

Esta versão passou por verificação de links, imagens, âncoras, templates, rotas administrativas, JavaScript, WhatsApp, menu mobile, montador de cardápio, disponibilidade e arquivos de publicação. O teste reutilizável está em `tests/qa_static.py`.


## Resultado dos testes de navegador

A versão final foi testada em tela de computador (1440 × 1000) e celular (390 × 844). Foram verificados menu, botões, modais, disponibilidade, montador de cardápio, mensagem do WhatsApp, link alternativo e as áreas demonstrativas do painel. Não foram encontrados erros de JavaScript, console ou rolagem horizontal.


## Segurança da publicação

- Na hospedagem, a variável `ADMIN_PASSWORD` é obrigatória.
- Se ela não estiver configurada no Render, o painel recusa o login em vez de aceitar a senha local de teste.
- Use uma senha longa e exclusiva e não a coloque no GitHub.
