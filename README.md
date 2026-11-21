# Representatividade Política e Financiamento Eleitoral

Pipeline da disciplina de Big Data para as eleições de 2024. A pergunta do trabalho compara quem se candidata (gênero, raça, cargo, partido e UF) com o dinheiro declarado na prestação de contas.

Fonte: Portal de Dados Abertos do TSE. Recorte: candidaturas, receitas e despesas contratadas de 2024, por UF.

O registro do que a disciplina pediu, do que já está no repositório e do que ainda falta está em [docs/DOCUMENTO\_DO\_PROJETO.md](docs/DOCUMENTO_DO_PROJETO.md).

Os dados públicos passam pelo tratamento, ficam no grão de uma candidatura e são carregados no PostgreSQL da Aiven. A infraestrutura nasce por Terraform. Um painel em Streamlit lê o banco e compara a fatia das candidaturas com a fatia do dinheiro. Credenciais não entram no repositório.

O tema se alinha à ODS 5 (igualdade de gênero) e à ODS 18 do guia da disciplina (igualdade étnico-racial).

## Integrantes

|Integrante|GitHub|
|-|-|
|Cauã Maia de Brito|[Caua-Maia](https://github.com/Caua-Maia)|
|João Pedro Santana|[JPedro-Santana](https://github.com/JPedro-Santana)|
|Sofia Santos de Mendonça|[xofia02](https://github.com/xofia02)|
|Kézia Carneiro Silva|[keziazcs](https://github.com/keziazcs)|

## Arquitetura

```mermaid
flowchart TD
  csvTse\[CSVs do TSE em etl/data\_raw]
  transform\[etl/02\_transform.py<br/>tratamento e LGPD]
  parquet\[Parquet e manifest.json<br/>etl/data\_processed]
  load\[etl/03\_load.py<br/>carga]
  terraform\[Terraform<br/>provider aiven/aiven]
  pg\[(PostgreSQL 18 na Aiven<br/>plano free-1-1gb)]
  cand\[candidatura]
  fin\[financiamento]
  perfil\[perfil]
  painel\[Painel Streamlit<br/>dashboard/painel/app.py]

  csvTse --> transform --> parquet --> load --> pg
  terraform -->|provisiona| pg
  pg --> cand
  pg --> fin
  pg --> perfil
  cand ---|1 para 1| fin
  cand --> painel
  fin --> painel
```

O fluxo é em lote. Os CSVs vêm do download do pleito, o tratamento roda UF por UF e só a base tratada vai para a nuvem. O Terraform cria o serviço. A carga só roda depois que o serviço está em Running e o `.env` aponta para ele.

## Estrutura do repositório

|Pasta|O que contém|
|-|-|
|`etl/`|Tratamento (`02\_transform.py`), carga (`03\_load.py`) e exploração|
|`dashboard/painel/`|Painel local que abre no navegador e lê o PostgreSQL da Aiven.|
|`terraform/`|Provisionamento do PostgreSQL|
|`docs/`|Decisões de LGPD e dicionário do tratamento|
|`requirements.txt`|Dependências Python|
|`.env.example`|Modelo da URI do banco, sem senha real|
|`terraform/terraform.tfvars.example`|Modelo do token da Aiven, sem token real|

Os CSVs brutos ficam em `etl/data\_raw/` e o parquet tratado em `etl/data\_processed/`. Os dois ficam fora do Git por tamanho. A base tratada se regenera com o script de tratamento.

## Dados utilizados

|Item|Descrição|
|-|-|
|Fonte|Portal de Dados Abertos do TSE|
|Base|Candidaturas (`consulta\_cand\_2024`) e prestação de contas eleitorais de candidatos 2024|
|Período|Eleições de 2024|
|Recorte|26 estados. O Distrito Federal não entra: o pleito de 2024 é municipal e o DF não tem municípios|
|Formato|CSV com separador `;` e encoding `latin-1`|
|Chave|`SQ\_CANDIDATO` em candidatos, receitas e despesas contratadas|

Arquivos usados:

* `consulta\_cand\_2024/consulta\_cand\_2024\_{UF}.csv`
* `prestacao\_de\_contas\_eleitorais\_candidatos\_2024/receitas\_candidatos\_2024\_{UF}.csv`
* `prestacao\_de\_contas\_eleitorais\_candidatos\_2024/despesas\_contratadas\_candidatos\_2024\_{UF}.csv`

Características que mudaram o desenho:

* A prestação de contas tem várias linhas por candidatura. O microdado bruto não cabe, e não precisa caber, no disco de 1 GB do plano gratuito.
* Prefeito de segundo turno aparece mais de uma vez em `consulta\_cand`.
* `despesas\_pagas` usa `SQ\_PRESTADOR\_CONTAS`. Não entra no cruzamento.
* Há CPF, CNPJ, e-mail, título de eleitor, data de nascimento e nome de doador ou fornecedor. Esses campos saem antes da gravação. Ver [docs/LGPD.md](docs/LGPD.md).

## Os 5 V's neste dataset

|V|Como aparece no projeto|
|-|-|
|Volume|Os CSVs brutos ocupam cerca de 5,7 GB e não cabem no disco de 1 GB do plano gratuito. O ETL reduz isso a 463.677 linhas por tabela e cerca de 14 MB de Parquet, com soma financeira por candidatura, corte de colunas e compressão colunar.|
|Variedade|Três estruturas tabulares com grãos diferentes: cadastro da candidatura (uma ou duas linhas por pessoa, por causa do segundo turno), receitas e despesas contratadas (vários lançamentos por pessoa). O valor monetário chega como texto no padrão brasileiro.|
|Velocidade|Processamento em lote, a partir do download dos arquivos do pleito. Não há API contínua. A prestação de contas é lida em blocos de 200 mil linhas, UF por UF.|
|Veracidade|A chave não passa por float. O segundo turno não duplica a candidatura. Sentinelas do TSE não viram categoria. Dinheiro usa decimal de centavos. A fixture sintética e `validar\_carga.py` conferem grão, LGPD, idade e o fechamento das somas.|
|Valor|O indicador compara a composição de quem concorre com a composição do recurso, por gênero e raça. É a leitura de equidade das ODS 5 e 18 aplicada ao dinheiro de campanha.|

## Tipos de dado

|Tipo|Onde aparece|
|-|-|
|Estruturado|CSVs do TSE, Parquet de candidatura e financiamento, tabelas `candidatura`, `financiamento` e `perfil` no PostgreSQL|
|Semi-estruturado|`manifest.json`, com contagens por UF, colunas geradas e colunas removidas por LGPD|
|Não estruturado|PDFs de leiaute publicados pelo TSE junto com os microdados. Servem de documentação da fonte e não entram na carga|

Dentro das tabelas, as variáveis se dividem em categóricas (gênero, raça, cargo, partido, UF, situação no turno), numéricas contínuas (receita e despesa em reais), numéricas discretas (idade, quantidade de lançamentos, turno) e identificadores (`sq\_candidato`).

## Tratamento realizado

Código: `etl/02\_transform.py` (a lógica está em `etl/transformar.py`).

|Problema encontrado|Decisão|Justificativa|
|-|-|-|
|`SQ\_CANDIDATO` pode virar float na leitura|Ler a chave como texto e só então converter para inteiro|Float altera identificador grande e o join falha em silêncio|
|Várias linhas por candidato na prestação de contas|Somar `VR\_RECEITA` e `VR\_DESPESA\_CONTRATADA` por `SQ\_CANDIDATO`|A pergunta é quanto cada candidatura movimentou, não cada lançamento|
|Candidato sem receita ou sem despesa|Left join a partir da candidatura e preencher com 0|Se quem não arrecadou sumir, a comparação entre perfil e dinheiro fica distorcida|
|Segundo turno repetido|Manter o maior `NR\_TURNO` de cada `SQ\_CANDIDATO`|O resultado final da campanha está no último turno|
|Marcadores `#NULO#`, `#NE#` e `-1`|Viram nulo. Idade negativa não vira zero|São ausências do TSE, não categorias|
|Vírgula decimal nos valores|Trocar vírgula por ponto e arredondar em centavos|O CSV oficial mistura os dois formatos|
|Mesmo rótulo em maiúsculas e minúsculas|Gênero, raça, cargo, partido, UF e situação em maiúsculas|Evita partir a mesma categoria em duas|
|Dados pessoais|Remover antes de gravar. Receitas e despesas são lidas só com chave e valor|O cruzamento não precisa de CPF. Nome de doador não entra na base analítica|
|Volume do arquivo de contas|Agregar em blocos de 200 mil linhas com Pandas|Uma linha por candidatura cabe no plano gratuito. PySpark não muda o resultado nesse grão|
|Situação da candidatura (apto, indeferido etc.)|Guardar a coluna, sem filtrar|O recorte "apenas aptos" é regra da análise seguinte|

A saída é uma linha por `SQ\_CANDIDATO`:

* `etl/data\_processed/candidatura.parquet`
* `etl/data\_processed/financiamento.parquet`
* `etl/data\_processed/manifest.json` com a contagem por UF

O nome de urna permanece. É o nome público da campanha. A data de nascimento sai. O arquivo de candidaturas de 2024 não traz `NR\_IDADE\_DATA\_POSSE`, então a idade é calculada em 1º de janeiro do ano seguinte à eleição e só esse número é gravado.

Conferência da lógica, com CSV sintético no formato do TSE (não é a base oficial):

```powershell
.\\venv\\Scripts\\python.exe etl\\verificar\_fixture.py
```

## Modelagem

### Escolha do banco

O banco é o PostgreSQL, relacional, no plano gratuito da Aiven. Os motivos:

* **O dado é tabular.** Depois do tratamento, cada candidatura é uma linha com colunas fixas. Não há documento aninhado nem esquema variável.
* **A chave é estável.** `sq\_candidato` liga candidatura e financiamento em 1 para 1, com chave primária e chave estrangeira garantindo a integridade.
* **A análise é agregação com join.** O indicador soma candidaturas e dinheiro por gênero, raça, cargo e UF. É o caso de uso típico de SQL.
* **Cabe no plano gratuito.** A base tratada ocupa poucos megabytes, longe do limite de 1 GB.

Um banco documental não acrescenta nada a esse grão. OpenSearch, opcional no guia, não foi provisionado: não há busca textual nem log semi-estruturado. Também não há tabela de lançamento. Cada doação estouraria o disco de 1 GB e guardaria dado pessoal de doador e fornecedor.

### Tabelas

```text
candidatura                          financiamento
-----------------------------        ---------------------------------
sq\_candidato  BIGINT  PK      1 -- 1 sq\_candidato           BIGINT PK/FK
ano\_eleicao   INTEGER                vr\_receita             NUMERIC(16,2)
sg\_uf         CHAR(2)                vr\_despesa\_contratada  NUMERIC(16,2)
nm\_ue         TEXT                   qt\_receitas            INTEGER
ds\_cargo      TEXT                   qt\_despesas            INTEGER
nm\_urna       TEXT
sg\_partido    TEXT
nm\_partido    TEXT
ds\_genero     TEXT
ds\_cor\_raca   TEXT
ds\_situacao\_candidatura TEXT
ds\_sit\_tot\_turno        TEXT
nr\_turno\_resultado      SMALLINT
nr\_idade\_data\_posse     SMALLINT
```

`financiamento.sq\_candidato` referencia `candidatura.sq\_candidato`. As duas tabelas têm a mesma quantidade de linhas (463.677).

A carga cria também a tabela `perfil`, agregada a partir do join das duas, no grão UF × gênero × raça × cargo. Há um índice em `candidatura (sg\_uf, ds\_cargo, ds\_genero, ds\_cor\_raca)` para essa leitura.

```text
perfil
---------------------------------
sg\_uf                  CHAR(2)
ds\_genero              TEXT
ds\_cor\_raca            TEXT
ds\_cargo               TEXT
qt\_candidaturas        INTEGER
vr\_receita             NUMERIC(16,2)
vr\_despesa\_contratada  NUMERIC(16,2)
```

### Dicionário de dados

`candidatura`: uma linha por candidatura.

|Campo|Tipo|Origem no TSE|Descrição|
|-|-|-|-|
|`sq\_candidato`|BIGINT, PK|`SQ\_CANDIDATO`|Identificador sequencial da candidatura. Chave de todo o modelo|
|`ano\_eleicao`|INTEGER|`ANO\_ELEICAO`|Ano do pleito (2024)|
|`sg\_uf`|CHAR(2)|`SG\_UF`|Sigla do estado|
|`nm\_ue`|TEXT|`NM\_UE`|Município da disputa|
|`ds\_cargo`|TEXT|`DS\_CARGO`|Vereador, prefeito ou vice-prefeito|
|`nm\_urna`|TEXT|`NM\_URNA\_CANDIDATO`|Nome público de campanha|
|`sg\_partido`|TEXT|`SG\_PARTIDO`|Sigla do partido|
|`nm\_partido`|TEXT|`NM\_PARTIDO`|Nome do partido|
|`ds\_genero`|TEXT|`DS\_GENERO`|Gênero declarado|
|`ds\_cor\_raca`|TEXT|`DS\_COR\_RACA`|Cor ou raça declarada|
|`ds\_sit\_tot\_turno`|TEXT|`DS\_SIT\_TOT\_TURNO`|Resultado no turno (eleito, não eleito, suplente etc.)|
|`nr\_turno\_resultado`|SMALLINT|`NR\_TURNO`|Maior turno disputado pela candidatura|
|`nr\_idade\_data\_posse`|SMALLINT|calculada de `DT\_NASCIMENTO`|Idade em 1º de janeiro de 2025. A data de nascimento não é armazenada|

`financiamento`: uma linha por candidatura, 1 para 1 com `candidatura`.

|Campo|Tipo|Origem no TSE|Descrição|
|-|-|-|-|
|`sq\_candidato`|BIGINT, PK e FK|`SQ\_CANDIDATO`|Liga o financiamento à candidatura|
|`vr\_receita`|NUMERIC(16,2)|soma de `VR\_RECEITA`|Total de receitas declaradas, em reais|
|`vr\_despesa\_contratada`|NUMERIC(16,2)|soma de `VR\_DESPESA\_CONTRATADA`|Total de despesas contratadas, em reais|
|`qt\_receitas`|INTEGER|contagem|Quantidade de lançamentos de receita|
|`qt\_despesas`|INTEGER|contagem|Quantidade de lançamentos de despesa contratada|

`perfil`: agregado por UF × gênero × raça × cargo, com `qt\_candidaturas` e as somas de `vr\_receita` e `vr\_despesa\_contratada` do grupo.

O detalhe operacional de cada coluna está em [docs/TRATAMENTO.md](docs/TRATAMENTO.md).

## Regras de negócio

Estas regras transformam o microdado em indicador. Estão no tratamento, na carga ou no painel.

1. **Grão da candidatura.** Uma linha por `SQ\_CANDIDATO`, com o dinheiro já somado.
2. **Resultado do último turno.** Se a mesma candidatura aparece duas vezes, fica a de maior `NR\_TURNO`.
3. **Dinheiro declarado.** `vr\_receita` soma `VR\_RECEITA` e `vr\_despesa\_contratada` soma `VR\_DESPESA\_CONTRATADA`, com precisão de centavos.
4. **Quem não movimentou permanece.** Candidatura sem lançamento recebe zero. Os percentuais usam o universo de quem concorreu.
5. **Órfão financeiro.** Lançamento sem candidatura na UF não entra na base analítica. A contagem fica no `manifest.json`.
6. **Sentinela não é categoria.** `#NULO#`, `#NE#`, `-1`, `-3` e `-4` viram nulo. Idade negativa ou acima de 120 também.
7. **Rótulo único.** Gênero, raça, cargo, partido, UF e situação no turno ficam em maiúsculas.
8. **Minimização (LGPD).** Dado pessoal sai antes do Parquet e antes da nuvem. A chave analítica é `SQ\_CANDIDATO`, não o CPF.
9. **Idade sem data.** A idade substitui a data de nascimento, com limite de 120 anos.
10. **Indicador do painel.** Para cada grupo:

    * fatia das candidaturas = candidaturas do grupo ÷ total do recorte;
    * fatia do dinheiro = dinheiro do grupo ÷ total do recorte;
    * diferença = fatia do dinheiro − fatia das candidaturas, em pontos percentuais.

    Diferença negativa quer dizer que o grupo concorre em proporção maior do que a do recurso que declara.

11. **Mulheres negras.** Seguindo o critério do IBGE, população negra é a soma de pretos e pardos. O KPI compara a fatia de mulheres pretas e pardas nas candidaturas com a fatia delas no dinheiro.
12. **Leitura da chapa.** Vice-prefeito aparece com quase nenhum dinheiro, porque a prestação da chapa costuma ser lançada no candidato a prefeito. O painel avisa isso e não apaga o vice.
13. **Faixa etária.** A idade é agrupada em até 29, 30–39, 40–49, 50–59 e 60 anos ou mais. Idade nula vira "sem informação".

## Infraestrutura

|Item|Escolha|
|-|-|
|Nuvem|Aiven, plano gratuito|
|Serviço|PostgreSQL (`aiven\_pg`)|
|Projeto Aiven|`cauamaia488-ead4`|
|Plano|`free-1-1gb`: 1 CPU, 1 GB de RAM, 1 GB de disco, até 20 conexões|
|Versão|PostgreSQL 18|
|Região|`do-sfo` (DigitalOcean, São Francisco), atribuída pela Aiven no plano gratuito e registrada no Terraform|
|Ferramenta|Terraform `>= 1.5` e provider `aiven/aiven` `4.x`|
|Arquivos|`terraform/main.tf`, `variables.tf`, `outputs.tf`|

O recurso provisionado é um único serviço PostgreSQL, `pg-1f18e561` (`aiven\_pg.tse`), com acesso público por SSL obrigatório. A carga (`etl/03\_load.py`) apaga e recria as duas tabelas a cada execução, então rodar de novo substitui os dados sem duplicar.

## Segurança das informações

Nenhum token, senha ou URI real é versionado.

|Segredo|Onde fica|O que entra no Git|
|-|-|-|
|Token da Aiven|`terraform/terraform.tfvars`, só na máquina de quem aplica|`terraform.tfvars.example`, com texto de exemplo|
|URI do PostgreSQL|`.env`, variável `DATABASE\_URL`|`.env.example`, com `SENHA` e `HOST` fictícios|
|Estado do Terraform|`.terraform/` e `\*.tfstate` na máquina local|Nada. O state guarda a senha do banco|

No código, o token é `var.aiven\_api\_token` com `sensitive = true`. A URI de saída do Terraform também é `sensitive`, para o `plan` e o `apply` não imprimirem a senha. O `.gitignore` bloqueia `.env`, `terraform.tfvars`, `.terraform/` e os arquivos de state.

## Execução

Ferramentas: Python 3, o conteúdo de `requirements.txt` (Pandas, PyArrow, SQLAlchemy, psycopg e python-dotenv) e Terraform 1.5 ou superior. Conta na Aiven com um projeto e um token pessoal.

```powershell
python -m venv venv
.\\venv\\Scripts\\Activate.ps1
pip install -r requirements.txt
```

Coloque os CSVs oficiais em `etl/data\_raw/`, nas pastas citadas em Dados utilizados.

```powershell
# Uma UF, para conferir
.\\venv\\Scripts\\python.exe etl\\02\_transform.py --uf AC

# Todas as UFs encontradas em data\_raw
.\\venv\\Scripts\\python.exe etl\\02\_transform.py
```

Infraestrutura, com o token só no arquivo local:

```powershell
copy terraform\\terraform.tfvars.example terraform\\terraform.tfvars
# Edite terraform.tfvars com o token (projeto e servico ja vem preenchidos). Nao commite esse arquivo.

cd terraform
terraform init
terraform plan
terraform apply
terraform output -raw postgresql\_service\_uri
```

Copie a URI para `.env` na raiz do projeto:

```text
DATABASE\_URL=postgres://avnadmin:...@....aivencloud.com:PORTA/defaultdb?sslmode=require
```

```powershell
.\\venv\\Scripts\\python.exe etl\\03\_load.py
```

O script imprime a quantidade de linhas de cada tabela e o tamanho do banco. Esses números mostram que a base coube no plano de 1 GB.

Para conferir a carga (as três tabelas existem, as somas de `perfil` fecham com `financiamento`, não há financiamento órfão nem idade impossível):

```powershell
.\\venv\\Scripts\\python.exe etl\\validar\_carga.py
```

## Painel

Painel publicado: *link do Streamlit Cloud (entra em 21/11)*

Para rodar localmente, com o serviço da Aiven em Running e o `.env` na raiz:

```powershell
.\\venv\\Scripts\\python.exe -m streamlit run dashboard\\painel\\app.py
```

Abre em http://localhost:8501. O painel lê `candidatura` e `financiamento` e agrega na hora. O cache da consulta dura cinco minutos.

O que a tela oferece:

* **Quatro KPIs no topo:** quantidade de candidaturas, total do dinheiro escolhido, média por candidatura (contando quem declarou zero) e a fatia do dinheiro que vai para mulheres negras, com a diferença em pontos percentuais em relação à fatia delas nas candidaturas.
* **Seletor de cargo:** todos, vereador, prefeito ou vice-prefeito.
* **Seletor de métrica:** receita ou despesa contratada. Os gráficos trocam a série do dinheiro conforme a escolha.
* **Filtros cruzados na barra lateral:** ano (fixo em 2024), região, estado, gênero, raça e faixa etária. Todos valem ao mesmo tempo.
* **Gráficos de gênero, raça e cargo:** barras comparando a fatia das candidaturas (azul) com a fatia do dinheiro (laranja).
* **Tabelas do recorte:** quantidade, valor em reais, os dois percentuais e a diferença em pontos percentuais.

Scripts anteriores de exploração, úteis para inspecionar o CSV cru: `etl/inspect\_sample.py`, `etl/validar\_merge.py` e `etl/01\_explore.py`. Eles não gravam a base tratada.

## Escopo e pendências

Fora do desenho, por decisão de escopo:

* OpenSearch, GitHub Actions e série histórica. A base cobre só o pleito municipal de 2024.
* `despesas\_pagas`, porque a chave dessa base é `SQ\_PRESTADOR\_CONTAS` e o join com a candidatura não fecha.

Em andamento até a entrega final (26/11):

* Publicação do painel no Streamlit Cloud.
* Gráfico cruzando gênero × raça e drill-down de estado para município.
* Ajuste da documentação da coluna `ds\_situacao\_candidatura`.
* Roteiro da apresentação.

O registro completo do que a disciplina pediu e do que foi entregue está em [docs/DOCUMENTO\_DO\_PROJETO.md](docs/DOCUMENTO_DO_PROJETO.md).

