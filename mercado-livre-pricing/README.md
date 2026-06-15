# Mercado Livre - Gestao de Precos e Produtos Campeoes

Sistema para:

1. **Gestao de preços** - monitora seus anuncios e os concorrentes no Mercado
   Livre e sugere (ou aplica) o preco ideal todos os dias, respeitando a sua
   margem minima.
2. **Produtos campeoes** - encontra produtos com alta demanda e baixa
   concorrencia, bons candidatos para vender.

Funciona em modo "somente leitura" usando apenas a **API publica** do
Mercado Livre (sem necessidade de credenciais). Para atualizar precos dos
seus proprios anuncios automaticamente, e necessario configurar credenciais
OAuth (veja abaixo).

## Instalacao

```bash
cd mercado-livre-pricing
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
cp config/products.example.json config/products.json
```

Edite `config/products.json` com os seus produtos (veja a estrutura de
campos em `src/models.py::ProductConfig`).

## Dashboard web (forma mais facil de usar)

Para acessar tudo por uma pagina no navegador, sem usar linha de comando:

```bash
python -m src.webapp
```

Isso inicia um servidor local. Abra no navegador:

- http://127.0.0.1:5000/ - relatorio de precos (tabela com piso, alvo, preco
  sugerido, margem, concorrentes e a acao recomendada para cada produto).
  Quando a acao for "reduzir" ou "aumentar", aparece um botao **Aplicar** que
  atualiza o preco no Mercado Livre (requer credenciais OAuth configuradas).
- http://127.0.0.1:5000/champions - busca de produtos campeoes (informe
  termos separados por virgula, ou deixe vazio para usar as tendencias
  atuais do Mercado Livre).

O servidor roda apenas na sua maquina (`127.0.0.1`) - ninguem de fora acessa.

## Uso diario (linha de comando)

### 1. Relatorio de precos

Para cada produto configurado, busca os concorrentes pelo `search_query`,
calcula o preco minimo viavel (sua margem minima), o preco-alvo (margem
desejada) e sugere um preco com base na estrategia escolhida:

```bash
python -m src.cli price-report --config config/products.json
```

Estrategias disponiveis por produto (`strategy` no JSON):

- `match_median` (padrao): acompanha a mediana dos concorrentes.
- `beat_lowest`: fica `competitiveness_step` abaixo do concorrente mais barato.
- `premium`: posiciona perto do topo do mercado, priorizando margem.

Em qualquer estrategia, o preco sugerido **nunca fica abaixo** do preco
minimo viavel (margem minima configurada).

O relatorio tambem e salvo em `data/price_report.csv`.

### 2. Encontrar produtos campeoes

Usa as tendencias de busca do Mercado Livre (ou termos que voce informar)
e pontua os resultados por `vendas / (1 + concorrentes)`, com bonus para
frete gratis:

```bash
# usando tendencias automaticas do site
python -m src.cli find-champions --top 15

# usando seus proprios termos
python -m src.cli find-champions --queries "tenis,fone bluetooth,capa celular" --top 15
```

Salva o ranking em `data/champions.csv`.

### 3. Aplicar precos sugeridos (requer autenticacao)

```bash
# modo simulacao (mostra o que faria, nao altera nada)
python -m src.cli apply-prices --config config/products.json

# aplica de fato
python -m src.cli apply-prices --config config/products.json --confirm
```

## Automatizando a rotina diaria

Sugestao de cron (roda todos os dias as 7h):

```cron
0 7 * * * cd /caminho/para/mercado-livre-pricing && .venv/bin/python -m src.cli price-report --config config/products.json
```

## Configurando credenciais (OAuth) - opcional

Necessario apenas para `apply-prices --confirm` e para usar
`item_id`/preco atual de anuncios privados.

1. Crie uma aplicacao em https://developers.mercadolibre.com.br/.
2. Preencha `ML_CLIENT_ID`, `ML_CLIENT_SECRET` e `ML_REDIRECT_URI` no `.env`.
3. Gere a URL de autorizacao:

   ```python
   from dotenv import load_dotenv
   load_dotenv()
   from src.ml_client import MLClient, MLCredentials
   client = MLClient(credentials=MLCredentials.from_env())
   print(client.get_authorization_url())
   ```

4. Abra a URL, autorize o app, copie o `code` retornado na URL de redirect.
5. Troque o code por tokens:

   ```python
   token_data = client.exchange_code_for_token("CODE_AQUI")
   print(token_data)  # salve access_token e refresh_token no .env
   ```

6. Coloque `access_token` e `refresh_token` em `ML_ACCESS_TOKEN` e
   `ML_REFRESH_TOKEN` no `.env`. O cliente renova o access_token
   automaticamente quando expira (usando o refresh_token).

## Testes

```bash
pip install pytest
pytest
```

## Estrutura

```
mercado-livre-pricing/
├── README.md
├── requirements.txt
├── .env.example
├── config/
│   └── products.example.json   # copie para products.json e edite
├── data/                        # relatorios gerados (CSV)
├── src/
│   ├── ml_client.py             # cliente da API do Mercado Livre (publica + OAuth)
│   ├── models.py                # dataclasses (ProductConfig, PriceSuggestion, ...)
│   ├── pricing_engine.py        # calculo de margem/preco e pontuacao de campeoes
│   ├── product_finder.py        # busca de produtos campeoes
│   ├── services.py              # funcoes compartilhadas (config, cliente, relatorio)
│   ├── cli.py                   # comandos: price-report, find-champions, apply-prices
│   ├── webapp.py                # dashboard web local (python -m src.webapp)
│   ├── templates/                # paginas HTML do dashboard
│   └── static/style.css
└── tests/
    └── test_pricing_engine.py
```
