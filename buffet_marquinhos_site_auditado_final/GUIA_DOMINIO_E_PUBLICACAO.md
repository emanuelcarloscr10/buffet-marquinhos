# Guia: domínio e publicação

## 1. Criar o repositório no GitHub

1. Entre no GitHub e crie uma conta.
2. Clique em `New repository`.
3. Nome sugerido: `buffet-do-marquinhos`.
4. Abra o repositório e escolha `Add file` > `Upload files`.
5. Extraia o ZIP no computador e envie todos os arquivos e pastas do projeto.
6. Confirme em `Commit changes`.

## 2. Publicar no Render

1. Crie uma conta no Render usando o GitHub.
2. No painel, clique em `New` > `Blueprint`.
3. Escolha o repositório `buffet-do-marquinhos`.
4. O Render reconhecerá o arquivo `render.yaml`.
5. Defina a variável `ADMIN_PASSWORD` com uma senha forte e guarde-a.
6. Confirme a publicação.
7. Aguarde o status `Live`.
8. Abra o endereço fornecido pelo Render.
9. Acrescente `/admin` ao final para entrar no painel.

Exemplo temporário:

- Site: `https://buffet-do-marquinhos.onrender.com`
- Painel: `https://buffet-do-marquinhos.onrender.com/admin`

## 3. Registrar um domínio `.com.br`

1. Entre no Registro.br.
2. Pesquise o nome desejado, por exemplo `buffetdomarquinhos.com.br`.
3. Somente prossiga se aparecer como disponível.
4. Crie ou entre na conta do titular.
5. Informe CPF ou CNPJ e os dados solicitados.
6. O Registro.br informa atualmente o valor de R$ 40,00 por ano; confirme o preço exibido antes de pagar.
7. Pague o período escolhido.

O registro do domínio e a hospedagem são serviços diferentes. O domínio é comprado no Registro.br; o site continua hospedado no Render.

## 4. Ligar o domínio ao Render

1. No Render, abra o serviço do site.
2. Entre em `Settings` > `Custom Domains`.
3. Adicione o domínio principal, por exemplo `buffetdomarquinhos.com.br`. O Render também prepara a versão com `www` e o redirecionamento correspondente.
4. O Render mostrará os registros DNS necessários.
5. No Registro.br, abra o domínio e entre em `DNS` > `Editar Zona`.
6. Remova registros `AAAA` conflitantes, caso existam, e copie exatamente os registros mostrados pelo Render.
7. Volte ao Render e clique em `Verify`.

A atualização do DNS pode levar algum tempo. Depois da confirmação, o Render ativa HTTPS automaticamente.

## 5. Uso diário depois de publicado

- Agenda: `seu-dominio.com.br/admin`
- Textos e preços: menu `Textos e preços`
- Pratos: menu `Cardápio`
- Fotos e capa: menu `Fotos`

Tudo que for salvo no painel aparece no site público.


## Versão pronta para publicação

- Aviso: 3 opções de sobremesas a cada 100 convidados.
- Aviso editável pelo painel em Textos e preços.
- Painel administrativo completo em `/admin`.
- Guia detalhado disponível em `PASSO_A_PASSO_PUBLICAR_E_USAR_ADMIN.md`.
