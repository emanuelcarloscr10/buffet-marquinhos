# Buffet do Marquinhos — domínio e publicação

O domínio `buffetdomarquinhos.com.br` já está ligado ao serviço `buffet-marquinhos`. Preserve esse mesmo Web Service para esta migração.

## Estrutura final

- GitHub: código.
- `buffet-marquinhos` no Render: aplicação Flask/Gunicorn.
- Render Postgres: todos os dados administrativos.
- Persistent Disk `/var/data`: uploads feitos pelo painel.
- Domínio: `buffetdomarquinhos.com.br`.

## Importante sobre plano pago

Para usar Persistent Disk, o **Instance Type do Web Service** precisa ser pago (por exemplo Starter). Isso é diferente do plano do workspace/conta.

## Variáveis de produção

No Web Service:

- `DATABASE_URL` = Internal Database URL do Render Postgres;
- `SECRET_KEY` = segredo longo e aleatório;
- `ADMIN_PASSWORD` = senha administrativa forte;
- `UPLOAD_ROOT=/var/data/uploads`;
- `BUSINESS_TIMEZONE=America/Sao_Paulo`.

Não coloque os valores secretos no GitHub.

## Atualizar sem perder cadastros

Depois da migração e do teste de persistência:

```bash
git add .
git commit -m "Descrição da alteração"
git push
```

O código é redeployado; os dados permanecem no PostgreSQL e os uploads permanecem no Persistent Disk.

## Verificação após deploy

Abra `/health` e confirme `status: ok`, `database: PostgreSQL`, `persistent: true` e o fuso de São Paulo. Depois abra `/admin` e confirme **Banco: PostgreSQL · Persistente**.

O roteiro completo está em `MIGRACAO_RENDER_PRODUCAO.md`.
