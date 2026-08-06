# Buffet do Marquinhos — publicação e painel administrativo

## Endereços planejados

O domínio definitivo sugerido é:

- Site público: `https://buffetdomarquinhos.com.br`
- Painel: `https://buffetdomarquinhos.com.br/admin`
- Login direto: `https://buffetdomarquinhos.com.br/admin/login`

Esses endereços somente funcionarão depois que o domínio for registrado e conectado à hospedagem.

Antes de conectar o domínio, o Render fornecerá um endereço temporário semelhante a:

- Site: `https://buffet-marquinhos-praia-grande-sc.onrender.com`
- Painel: `https://buffet-marquinhos-praia-grande-sc.onrender.com/admin`

O nome exato do endereço temporário pode mudar se já estiver sendo usado por outra conta.

---

## O que pode ser feito no painel

### Agenda
- cadastrar evento;
- informar data e horário;
- informar nome, telefone, cidade, local e convidados;
- marcar como reservado, confirmado ou cancelado;
- editar e excluir eventos;
- bloquear e desbloquear datas;
- alterar a capacidade máxima diária.

### Textos e preços
- trocar telefone, endereço, Instagram e CNPJ;
- editar todos os principais textos;
- alterar a história do buffet;
- editar a regra das sobremesas;
- editar o aviso de deslocamento;
- alterar pacotes e preços;
- trocar logo e cardápio oficial.

### Cardápio
- criar categorias;
- adicionar e editar opções;
- esconder itens;
- reorganizar a ordem;
- excluir opções.

### Fotos
- enviar fotos pelo celular ou computador;
- definir categoria;
- alterar a ordem;
- ocultar ou excluir;
- escolher fotos da capa e da seção “Nossa história”.

---

# PARTE 1 — colocar o projeto no GitHub

## 1. Baixar e extrair

1. Baixe o arquivo ZIP entregue pelo ChatGPT.
2. Extraia o arquivo no computador.
3. Abra a pasta extraída.
4. Confirme que `app.py`, `render.yaml`, `requirements.txt`, `templates` e `static` estão no mesmo nível.

Não envie o ZIP fechado para o Render.

## 2. Criar o repositório

1. Acesse o GitHub e crie uma conta.
2. Clique no símbolo `+`.
3. Escolha **New repository**.
4. Use o nome `buffet-marquinhos`.
5. Pode escolher repositório privado.
6. Clique em **Create repository**.

## 3. Enviar os arquivos

1. Dentro do repositório, clique em **Add file**.
2. Escolha **Upload files**.
3. Arraste todos os arquivos e pastas que estavam dentro da pasta extraída.
4. O arquivo `render.yaml` precisa ficar na raiz do repositório.
5. Clique em **Commit changes**.

Nunca coloque a senha do painel dentro dos arquivos ou do GitHub.

---

# PARTE 2 — publicar no Render

Este projeto usa agenda, banco de dados e envio de fotos. Por isso, ele precisa de armazenamento persistente.

## 1. Criar a hospedagem

1. Crie uma conta no Render.
2. Conecte a conta do GitHub.
3. No painel do Render, clique em **New**.
4. Escolha **Blueprint**.
5. Selecione o repositório `buffet-marquinhos`.
6. Confirme o uso do arquivo `render.yaml`.

## 2. Definir a senha administrativa

Durante a criação, o Render solicitará a variável:

`ADMIN_PASSWORD`

Digite uma senha forte e exclusiva. Exemplo de formato:

`Buffet-Agenda-2026!UmaSenhaMaior`

Não use esse exemplo literalmente.

A variável `SECRET_KEY` será gerada automaticamente.

## 3. Confirmar o plano

O projeto está configurado com:

- serviço Python;
- plano `starter`;
- disco persistente de 1 GB;
- banco SQLite armazenado no disco;
- pasta permanente para fotos enviadas pelo painel.

O plano gratuito não é apropriado para esta configuração, porque não preserva os arquivos locais do painel.

## 4. Aguardar a publicação

O Render fará:

1. instalação das bibliotecas;
2. criação do banco de dados;
3. inicialização do site;
4. criação do endereço temporário.

Aguarde o status **Live**.

## 5. Testar

1. Abra o endereço temporário.
2. Acrescente `/admin`.
3. Entre com a senha definida em `ADMIN_PASSWORD`.
4. Cadastre um evento de teste.
5. Abra o site em outra aba e consulte a data.
6. Troque um texto e salve.
7. Envie uma foto de teste.
8. Exclua os testes depois.

---

# PARTE 3 — registrar o domínio

## Domínio sugerido

`buffetdomarquinhos.com.br`

A disponibilidade precisa ser confirmada no momento da compra. O arquivo do site não registra nem reserva o domínio automaticamente.

## Registro

1. Acesse o Registro.br.
2. Pesquise `buffetdomarquinhos.com.br`.
3. Se estiver disponível, clique para registrar.
4. Crie ou acesse sua conta.
5. Informe o CPF ou CNPJ do titular.
6. Confirme os dados.
7. O Registro.br informa atualmente o valor de R$ 40,00 por ano; confirme o valor exibido.
8. Faça o pagamento.

Guarde o acesso ao Registro.br, pois ele controla a propriedade do endereço.

---

# PARTE 4 — conectar o domínio ao Render

1. No Render, abra o serviço do Buffet do Marquinhos.
2. Entre em **Settings**.
3. Procure **Custom Domains**.
4. Clique em **Add Custom Domain**.
5. Informe `buffetdomarquinhos.com.br`. O Render também prepara a versão com `www` e o redirecionamento.
6. O Render mostrará quais registros DNS devem ser criados.
7. Abra o domínio no Registro.br.
8. Entre em **DNS** e depois em **Editar zona**.
9. Remova registros `AAAA` conflitantes, caso existam, e copie exatamente os registros fornecidos pelo Render.
10. Volte ao Render.
11. Clique em **Verify**.

A propagação pode levar algum tempo. Depois da verificação, o endereço será:

- `https://buffetdomarquinhos.com.br`
- `https://buffetdomarquinhos.com.br/admin`

O certificado HTTPS é administrado pelo Render.

---

# Como usar no dia a dia

## Cadastrar uma reserva

1. Acesse `/admin`.
2. Abra **Agenda**.
3. Clique em **Novo evento**.
4. Preencha data e horário.
5. Escolha `Reservado` ou `Confirmado`.
6. Salve.

Ao cadastrar o primeiro evento, o site mostrará a última vaga. Ao cadastrar o segundo, mostrará a agenda lotada.

## Editar uma palavra

1. Acesse `/admin`.
2. Entre em **Textos e preços**.
3. Altere o campo desejado.
4. Clique em **Salvar textos e contatos**.

## Trocar uma foto

1. Acesse `/admin`.
2. Entre em **Fotos**.
3. Envie a nova imagem.
4. Escolha a categoria.
5. Ajuste a ordem.
6. Oculte ou exclua a imagem antiga.

## Alterar o cardápio

1. Acesse `/admin`.
2. Entre em **Cardápio**.
3. Edite, adicione, esconda ou reorganize itens.
4. Salve.

---

# Alterar a senha futuramente

1. Abra o serviço no Render.
2. Entre em **Environment**.
3. Localize `ADMIN_PASSWORD`.
4. Troque o valor.
5. Salve.
6. Aguarde a nova publicação.

Não é necessário alterar código.

---

# Atualizações grandes no design

Fotos, agenda, textos, preços e cardápio podem ser administrados pelo painel. Alterações estruturais — como criar uma página nova ou mudar completamente o desenho — ainda exigem atualização do projeto no GitHub. Quando houver um novo commit, o Render publica a atualização automaticamente.
