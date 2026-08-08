# Migração segura para produção persistente no Render

Este guia é para o **Web Service já existente `buffet-marquinhos`**, que já atende `buffetdomarquinhos.com.br`. Preserve esse serviço e o domínio. Não crie outro Web Service para esta revisão.

## Antes de qualquer coisa

**Não recadastre a agenda real ainda.**

Os eventos que desapareceram do SQLite efêmero **não são recuperados automaticamente** ao criar o PostgreSQL. O ZIP enviado também não contém o banco que estava rodando temporariamente no Render. Se ainda existir algum dado importante somente no painel atual, anote/extraia esse dado antes de trocar o banco.

Esta versão possui **modo de proteção**: no Render, enquanto `DATABASE_URL` não apontar para PostgreSQL, o site público continua disponível, mas as gravações administrativas são bloqueadas para impedir uma nova perda de dados.

A produção só deve ser usada para cadastros reais quando o painel mostrar:

**Banco: PostgreSQL · Persistente**

## Ordem segura para o serviço existente

### 1. Mude o INSTANCE TYPE do Web Service para pago

No serviço `buffet-marquinhos`, altere o **Instance Type** de Free para **Starter** (ou superior).

Atenção: mudar somente o plano do workspace/conta não transforma automaticamente um Web Service Free em uma instância paga. O que interessa aqui é o Instance Type do próprio serviço.

### 2. Crie um Render Postgres pago, na mesma região

- Nome sugerido: `buffet-marquinhos-db`
- Instance Type: `Basic-256mb` já é suficiente para começar neste projeto
- Região: a mesma do Web Service
- Armazenamento: o padrão Basic já é amplo para este site

Guarde o **Internal Database URL**. Não coloque esse endereço no GitHub.

**Ainda não altere `DATABASE_URL` do Web Service.** Primeiro publique o código desta revisão, porque ele inclui o driver PostgreSQL (`psycopg`).

### 3. Adicione um Persistent Disk ao Web Service

No serviço `buffet-marquinhos`:

- Mount Path: `/var/data`
- Tamanho inicial: 1 GB
- Environment: `UPLOAD_ROOT=/var/data/uploads`

O PostgreSQL guardará agenda, cardápio, textos, preços e configurações. O disco persistente será usado somente para arquivos enviados pelo painel (fotos, logo e imagem do cardápio oficial).

### 4. Configure as variáveis obrigatórias

Em **Environment** do Web Service:

- `SECRET_KEY` = valor longo, aleatório e secreto
- `ADMIN_PASSWORD` = senha forte e exclusiva
- `UPLOAD_ROOT=/var/data/uploads`
- `BUSINESS_TIMEZONE=America/Sao_Paulo`

Nunca salve `SECRET_KEY`, `ADMIN_PASSWORD` ou a URL real do banco no GitHub.

### 5. Publique esta versão do código PRIMEIRO

Substitua os arquivos do projeto pela versão revisada, faça commit e push e aguarde o deploy.

Se ainda não houver PostgreSQL conectado, o painel mostrará **Modo de proteção**. Isso é proposital. Não tente cadastrar eventos nesse intervalo.

### 6. Conecte o PostgreSQL

Depois que a nova versão estiver no ar:

1. Abra `buffet-marquinhos` > Environment.
2. Crie/edite `DATABASE_URL`.
3. Use o **Internal Database URL** do Render Postgres.
4. Salve e aguarde o novo deploy.

A aplicação aceita a URL `postgresql://...` do Render e usa `psycopg` automaticamente.

### 7. Confirme a saúde da produção

Abra:

`https://buffetdomarquinhos.com.br/health`

A resposta precisa indicar:

- `status: ok`
- `database: PostgreSQL`
- `persistent: true`
- `timezone: America/Sao_Paulo`

Depois abra `/admin` e confirme que aparece **Banco: PostgreSQL · Persistente**, sem aviso de Modo de proteção.

## Teste obrigatório antes de recadastrar a agenda real

1. Cadastre um evento fictício.
2. Atualize a página (F5) e confirme que continua lá.
3. Faça um novo deploy do mesmo código.
4. Volte à Agenda e confirme que continua lá.
5. Edite o evento, atualize a página e confirme a edição.
6. Exclua o evento fictício.
7. Altere um texto e um item do cardápio, faça outro deploy e confirme que as alterações continuam.
8. Envie uma foto de teste pelo painel, faça deploy e confirme que a foto continua abrindo.

Somente depois desse teste recadastre a agenda real.

## Teste do cardápio

No site público, confirme:

- Pacote define **com/sem entrada** e **com/sem sobremesa**.
- Entrada: informativa; não existe escolha prato por prato.
- Massas: exatamente 1 opção.
- Strogonoff: exatamente 1 entre Carne e Frango.
- Lasanha: exatamente 1 sabor.
- Sobremesas: até 3 opções por bloco iniciado de 100 convidados.
- Churrasco: informativo; sem checkbox.
- Saladas: informativo; informa oito variedades, incluindo folhas, legumes e vinagrete; sem checkbox.
- Incluso: informativo; sem checkbox.
- Não existe botão global “Selecionar tudo”.

Essas regras também podem ser alteradas depois pelo painel Cardápio. Cada categoria tem **Tipo** e **Quando aparece**.

## Teste do WhatsApp

Teste em um celular real e também no computador:

1. preencha o orçamento;
2. escolha o pacote;
3. faça as escolhas obrigatórias do cardápio;
4. toque em **Enviar pelo WhatsApp**;
5. confirme que o WhatsApp abre com a mensagem pronta.

O envio final usa `wa.me` sem `fetch/await` entre o toque e a navegação. Se o navegador não abrir automaticamente, o formulário mostra um link alternativo.

## Backups

Depois de colocar o PostgreSQL pago em produção:

- use a área **Recovery** do Render Postgres para recuperação point-in-time quando necessário;
- gere exportações lógicas periódicas para guardar uma cópia fora do Render;
- antes de mudanças grandes, gere uma exportação adicional;
- não exclua o Persistent Disk enquanto houver fotos enviadas pelo painel.

## O que persiste onde

- **PostgreSQL:** agenda, bloqueios, capacidade, textos, preços, pacotes, cardápio, regras, equipe e metadados das fotos.
- **Persistent Disk `/var/data`:** arquivos enviados pelo painel.
- **GitHub:** código e imagens que já fazem parte do projeto.
