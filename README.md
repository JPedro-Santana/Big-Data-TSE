# Representatividade Política e Financiamento Eleitoral

Pipeline da disciplina de Big Data para as eleições de 2024. A pergunta do trabalho compara quem se candidata (gênero, raça, cargo, partido e UF) com o dinheiro declarado na prestação de contas.

Fonte: Portal de Dados Abertos do TSE. Recorte: candidaturas, receitas e despesas contratadas de 2024, por UF.

O registro do que a disciplina pediu, do que já está no repositório e do que ainda falta está em [docs/DOCUMENTO_DO_PROJETO.md](docs/DOCUMENTO_DO_PROJETO.md).

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
  csvTse[CSVs do TSE em etl/data_raw]
  transform[etl/02_transform.py<br/>tratamento e LGPD]
  parquet[Parquet e manifest.json<br/>etl/data_processed]
  load[etl/03_load.py<br/>carga]
  terraform[Terraform<br/>provider aiven/aiven]
  pg[(PostgreSQL 18 na Aiven<br/>plano free-1-1gb)]
  cand[candidatura]
  fin[financiamento]
  perfil[perfil]
  painel[Painel Streamlit<br/>dashboard/painel/app.py]

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
|`etl/`|Tratamento (`02_transform.py`), carga (`03_load.py`) e exploração|
|`dashboard/painel/`|Painel local que abre no navegador e lê o PostgreSQL da Aiven.|
|`terraform/`|Provisionamento do PostgreSQL|
|`docs/`|Decisões de LGPD e dicionário do tratamento|
|`requirements.txt`|Dependências Python|
|`.env.example`|Modelo da URI do banco, sem senha real|
|`terraform/terraform.tfvars.example`|Modelo do token da Aiven, sem token real|

Os CSVs brutos ficam em `etl/data_raw/` e o parquet tratado em `etl/data_processed/`. Os dois ficam fora do Git por tamanho. A base tratada se regenera com o script de tratamento.

## Dados utilizados

|Item|Descrição|
|-|-|
|Fonte|Portal de Dados Abertos do TSE|
|Base|Candidaturas (`consulta_cand_2024`) e prestação de contas eleitorais de candidatos 2024|
|Período|Eleições de 2024|
|Recorte|26 estados. O Distrito Federal não entra: o pleito de 2024 é municipal e o DF não tem municípios|
|Formato|CSV com separador `;` e encoding `latin-1`|
|Chave|`SQ_CANDIDATO` em candidatos, receitas e despesas contratadas|

Arquivos usados:

* `consulta_cand_2024/consulta_cand_2024_{UF}.csv`
* `prestacao_de_contas_eleitorais_candidatos_2024/receitas_candidatos_2024_{UF}.csv`
* `prestacao_de_contas_eleitorais_candidatos_2024/despesas_contratadas_candidatos_2024_{UF}.csv`

Características que mudaram o desenho:

* A prestação de contas tem várias linhas por candidatura. O microdado bruto não cabe, e não precisa caber, no disco de 1 GB do plano gratuito.
* Prefeito de segundo turno aparece mais de uma vez em `consulta_cand`.
* `despesas_pagas` usa `SQ_PRESTADOR_CONTAS`. Não entra no cruzamento.
* Há CPF, CNPJ, e-mail, título de eleitor, data de nascimento e nome de doador ou fornecedor. Esses campos saem antes da gravação. Ver [docs/LGPD.md](docs/LGPD.md).

## Os 5 V's neste dataset

|V|Como aparece no projeto|
|-|-|
|Volume|Os CSVs brutos ocupam cerca de 5,7 GB e não cabem no disco de 1 GB do plano gratuito. O ETL reduz isso a 463.677 linhas por tabela e cerca de 14 MB de Parquet, com soma financeira por candidatura, corte de colunas e compressão colunar.|
|Variedade|Três estruturas tabulares com grãos diferentes: cadastro da candidatura (uma ou duas linhas por pessoa, por causa do segundo turno), receitas e despesas contratadas (vários lançamentos por pessoa). O valor monetário chega como texto no padrão brasileiro.|
|Velocidade|Processamento em lote, a partir do download dos arquivos do pleito. Não há API contínua. A prestação de contas é lida em blocos de 200 mil linhas, UF por UF.|
|Veracidade|A chave não passa por float. O segundo turno não duplica a candidatura. Sentinelas do TSE não viram categoria. Dinheiro usa decimal de centavos. A fixture sintética e `validar_carga.py` conferem grão, LGPD, idade e o fechamento das somas.|
|Valor|O indicador compara a composição de quem concorre com a composição do recurso, por gênero e raça. É a leitura de equidade das ODS 5 e 18 aplicada ao dinheiro de campanha.|

## Tipos de dado

|Tipo|Onde aparece|
|-|-|
|Estruturado|CSVs do TSE, Parquet de candidatura e financiamento, tabelas `candidatura`, `financiamento` e `perfil` no PostgreSQL|
|Semi-estruturado|`manifest.json`, com contagens por UF, colunas geradas e colunas removidas por LGPD|
|Não estruturado|PDFs de leiaute publicados pelo TSE junto com os microdados. Servem de documentação da fonte e não entram na carga|

Dentro das tabelas, as variáveis se dividem em categóricas (gênero, raça, cargo, partido, UF, situação no turno), numéricas contínuas (receita e despesa em reais), numéricas discretas (idade, quantidade de lançamentos, turno) e identificadores (`sq_candidato`).

## Tratamento realizado

Código: `etl/02_transform.py` (a lógica está em `etl/transformar.py`).

|Problema encontrado|Decisão|Justificativa|
|-|-|-|
|`SQ_CANDIDATO` pode virar float na leitura|Ler a chave como texto e só então converter para inteiro|Float altera identificador grande e o join falha em silêncio|
|Várias linhas por candidato na prestação de contas|Somar `VR_RECEITA` e `VR_DESPESA_CONTRATADA` por `SQ_CANDIDATO`|A pergunta é quanto cada candidatura movimentou, não cada lançamento|
|Candidato sem receita ou sem despesa|Left join a partir da candidatura e preencher com 0|Se quem não arrecadou sumir, a comparação entre perfil e dinheiro fica distorcida|
|Segundo turno repetido|Manter o maior `NR_TURNO` de cada `SQ_CANDIDATO`|O resultado final da campanha está no último turno|
|Marcadores `#NULO#`, `#NE#` e `-1`|Viram nulo. Idade negativa não vira zero|São ausências do TSE, não categorias|
|Vírgula decimal nos valores|Trocar vírgula por ponto e arredondar em centavos|O CSV oficial mistura os dois formatos|
|Mesmo rótulo em maiúsculas e minúsculas|Gênero, raça, cargo, partido, UF e situação em maiúsculas|Evita partir a mesma categoria em duas|
|Dados pessoais|Remover antes de gravar. Receitas e despesas são lidas só com chave e valor|O cruzamento não precisa de CPF. Nome de doador não entra na base analítica|
|Volume do arquivo de contas|Agregar em blocos de 200 mil linhas com Pandas|Uma linha por candidatura cabe no plano gratuito. PySpark não muda o resultado nesse grão|
|Situação da candidatura (apto, indeferido etc.)|Não entra na base nesta versão|O painel conta todas as candidaturas registradas. Filtrar só as aptas exige reprocessar a base |

A saída é uma linha por `SQ_CANDIDATO`:

* `etl/data_processed/candidatura.parquet`
* `etl/data_processed/financiamento.parquet`
* `etl/data_processed/manifest.json` com a contagem por UF

O nome de urna permanece. É o nome público da campanha. A data de nascimento sai. O arquivo de candidaturas de 2024 não traz `NR_IDADE_DATA_POSSE`, então a idade é calculada em 1º de janeiro do ano seguinte à eleição e só esse número é gravado.

Conferência da lógica, com CSV sintético no formato do TSE (não é a base oficial):

```powershell
.\venv\Scripts\python.exe etl\verificar_fixture.py
```

## Modelagem

### Escolha do banco

O banco é o PostgreSQL, relacional, no plano gratuito da Aiven. Os motivos:

* **O dado é tabular.** Depois do tratamento, cada candidatura é uma linha com colunas fixas. Não há documento aninhado nem esquema variável.
* **A chave é estável.** `sq_candidato` liga candidatura e financiamento em 1 para 1, com chave primária e chave estrangeira garantindo a integridade.
* **A análise é agregação com join.** O indicador soma candidaturas e dinheiro por gênero, raça, cargo e UF. É o caso de uso típico de SQL.
* **Cabe no plano gratuito.** A base tratada ocupa poucos megabytes, longe do limite de 1 GB.

Um banco documental não acrescenta nada a esse grão. OpenSearch, opcional no guia, não foi provisionado: não há busca textual nem log semi-estruturado. Também não há tabela de lançamento. Cada doação estouraria o disco de 1 GB e guardaria dado pessoal de doador e fornecedor.

### Tabelas

```text
candidatura                          financiamento
-----------------------------        ---------------------------------
sq_candidato  BIGINT  PK      1 -- 1 sq_candidato           BIGINT PK/FK
ano_eleicao   INTEGER                vr_receita             NUMERIC(16,2)
sg_uf         CHAR(2)                vr_despesa_contratada  NUMERIC(16,2)
nm_ue         TEXT                   qt_receitas            INTEGER
ds_cargo      TEXT                   qt_despesas            INTEGER
nm_urna       TEXT
sg_partido    TEXT
nm_partido    TEXT
ds_genero     TEXT
ds_cor_raca   TEXT
ds_sit_tot_turno        TEXT
nr_turno_resultado      SMALLINT
nr_idade_data_posse     SMALLINT
```

`financiamento.sq_candidato` referencia `candidatura.sq_candidato`. As duas tabelas têm a mesma quantidade de linhas (463.677).

A carga cria também a tabela `perfil`, agregada a partir do join das duas, no grão UF × gênero × raça × cargo. Há um índice em `candidatura (sg_uf, ds_cargo, ds_genero, ds_cor_raca)` para essa leitura.

```text
perfil
---------------------------------
sg_uf                  CHAR(2)
ds_genero              TEXT
ds_cor_raca            TEXT
ds_cargo               TEXT
qt_candidaturas        INTEGER
vr_receita             NUMERIC(16,2)
vr_despesa_contratada  NUMERIC(16,2)
```

### Dicionário de dados

`candidatura`: uma linha por candidatura.

|Campo|Tipo|Origem no TSE|Descrição|
|-|-|-|-|
|`sq_candidato`|BIGINT, PK|`SQ_CANDIDATO`|Identificador sequencial da candidatura. Chave de todo o modelo|
|`ano_eleicao`|INTEGER|`ANO_ELEICAO`|Ano do pleito (2024)|
|`sg_uf`|CHAR(2)|`SG_UF`|Sigla do estado|
|`nm_ue`|TEXT|`NM_UE`|Município da disputa|
|`ds_cargo`|TEXT|`DS_CARGO`|Vereador, prefeito ou vice-prefeito|
|`nm_urna`|TEXT|`NM_URNA_CANDIDATO`|Nome público de campanha|
|`sg_partido`|TEXT|`SG_PARTIDO`|Sigla do partido|
|`nm_partido`|TEXT|`NM_PARTIDO`|Nome do partido|
|`ds_genero`|TEXT|`DS_GENERO`|Gênero declarado|
|`ds_cor_raca`|TEXT|`DS_COR_RACA`|Cor ou raça declarada|
|`ds_sit_tot_turno`|TEXT|`DS_SIT_TOT_TURNO`|Resultado no turno (eleito, não eleito, suplente etc.)|
|`nr_turno_resultado`|SMALLINT|`NR_TURNO`|Maior turno disputado pela candidatura|
|`nr_idade_data_posse`|SMALLINT|calculada de `DT_NASCIMENTO`|Idade em 1º de janeiro de 2025. A data de nascimento não é armazenada|

`financiamento`: uma linha por candidatura, 1 para 1 com `candidatura`.

|Campo|Tipo|Origem no TSE|Descrição|
|-|-|-|-|
|`sq_candidato`|BIGINT, PK e FK|`SQ_CANDIDATO`|Liga o financiamento à candidatura|
|`vr_receita`|NUMERIC(16,2)|soma de `VR_RECEITA`|Total de receitas declaradas, em reais|
|`vr_despesa_contratada`|NUMERIC(16,2)|soma de `VR_DESPESA_CONTRATADA`|Total de despesas contratadas, em reais|
|`qt_receitas`|INTEGER|contagem|Quantidade de lançamentos de receita|
|`qt_despesas`|INTEGER|contagem|Quantidade de lançamentos de despesa contratada|

`perfil`: agregado por UF × gênero × raça × cargo, com `qt_candidaturas` e as somas de `vr_receita` e `vr_despesa_contratada` do grupo.

O detalhe operacional de cada coluna está em [docs/TRATAMENTO.md](docs/TRATAMENTO.md).

## Regras de negócio

Estas regras transformam o microdado em indicador. Estão no tratamento, na carga ou no painel.

1. **Grão da candidatura.** Uma linha por `SQ_CANDIDATO`, com o dinheiro já somado.
2. **Resultado do último turno.** Se a mesma candidatura aparece duas vezes, fica a de maior `NR_TURNO`.
3. **Dinheiro declarado.** `vr_receita` soma `VR_RECEITA` e `vr_despesa_contratada` soma `VR_DESPESA_CONTRATADA`, com precisão de centavos.
4. **Quem não movimentou permanece.** Candidatura sem lançamento recebe zero. Os percentuais usam o universo de quem concorreu.
5. **Órfão financeiro.** Lançamento sem candidatura na UF não entra na base analítica. A contagem fica no `manifest.json`.
6. **Sentinela não é categoria.** `#NULO#`, `#NE#`, `-1`, `-3` e `-4` viram nulo. Idade negativa ou acima de 120 também.
7. **Rótulo único.** Gênero, raça, cargo, partido, UF e situação no turno ficam em maiúsculas.
8. **Minimização (LGPD).** Dado pessoal sai antes do Parquet e antes da nuvem. A chave analítica é `SQ_CANDIDATO`, não o CPF.
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
|Serviço|PostgreSQL (`aiven_pg`)|
|Projeto Aiven|`cauamaia488-ead4`|
|Plano|`free-1-1gb`: 1 CPU, 1 GB de RAM, 1 GB de disco, até 20 conexões|
|Versão|PostgreSQL 18|
|Região|`do-sfo` (DigitalOcean, São Francisco), atribuída pela Aiven no plano gratuito e registrada no Terraform|
|Ferramenta|Terraform `>= 1.5` e provider `aiven/aiven` `4.x`|
|Arquivos|`terraform/main.tf`, `variables.tf`, `outputs.tf`|

O recurso provisionado é um único serviço PostgreSQL, `pg-1f18e561` (`aiven_pg.tse`), com acesso público por SSL obrigatório. A carga (`etl/03_load.py`) apaga e recria as duas tabelas a cada execução, então rodar de novo substitui os dados sem duplicar.

## Segurança das informações

Nenhum token, senha ou URI real é versionado.

|Segredo|Onde fica|O que entra no Git|
|-|-|-|
|Token da Aiven|`terraform/terraform.tfvars`, só na máquina de quem aplica|`terraform.tfvars.example`, com texto de exemplo|
|URI do PostgreSQL|`.env`, variável `DATABASE_URL`|`.env.example`, com `SENHA` e `HOST` fictícios|
|Estado do Terraform|`.terraform/` e `*.tfstate` na máquina local|Nada. O state guarda a senha do banco|

No código, o token é `var.aiven_api_token` com `sensitive = true`. A URI de saída do Terraform também é `sensitive`, para o `plan` e o `apply` não imprimirem a senha. O `.gitignore` bloqueia `.env`, `terraform.tfvars`, `.terraform/` e os arquivos de state.

## Execução

Ferramentas: Python 3, o conteúdo de `requirements.txt` (Pandas, PyArrow, SQLAlchemy, psycopg e python-dotenv) e Terraform 1.5 ou superior. Conta na Aiven com um projeto e um token pessoal.

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Coloque os CSVs oficiais em `etl/data_raw/`, nas pastas citadas em Dados utilizados.

```powershell
# Uma UF, para conferir
.\venv\Scripts\python.exe etl\02_transform.py --uf AC

# Todas as UFs encontradas em data_raw
.\venv\Scripts\python.exe etl\02_transform.py
```

Infraestrutura, com o token só no arquivo local:

```powershell
copy terraform\terraform.tfvars.example terraform\terraform.tfvars
# Edite terraform.tfvars com o token (projeto e servico ja vem preenchidos). Nao commite esse arquivo.

cd terraform
terraform init
terraform plan
terraform apply
terraform output -raw postgresql_service_uri
```

Copie a URI para `.env` na raiz do projeto:

```text
DATABASE_URL=postgres://avnadmin:...@....aivencloud.com:PORTA/defaultdb?sslmode=require
```

```powershell
.\venv\Scripts\python.exe etl\03_load.py
```

O script imprime a quantidade de linhas de cada tabela e o tamanho do banco. Esses números mostram que a base coube no plano de 1 GB.

Para conferir a carga (as três tabelas existem, as somas de `perfil` fecham com `financiamento`, não há financiamento órfão nem idade impossível):

```powershell
.\venv\Scripts\python.exe etl\validar_carga.py
```

## Painel

Painel publicado: https://big-data-tse-trabalho.streamlit.app/

O painel consulta o PostgreSQL da Aiven a cada uso: os números vêm do banco na hora, sem arquivo intermediário.

Para rodar localmente, com o serviço da Aiven em Running e o `.env` na raiz:

```powershell
.\venv\Scripts\python.exe -m streamlit run dashboard\painel\app.py
```

Abre em http://localhost:8501. O painel lê `candidatura` e `financiamento` e agrega na hora. O cache da consulta dura cinco minutos.

### Interface

```mermaid
flowchart LR
  lateral["Barra lateral: filtros cruzados<br/>Ano 2024 · Região · Estado<br/>Gênero · Raça/cor · Faixa etária"]
  subgraph principal["Área principal, de cima para baixo"]
    direction TB
    topo["Seletores: Cargo e Dinheiro<br/>receita ou despesa contratada"]
    kpis["4 indicadores<br/>candidaturas · dinheiro · média · mulheres negras"]
    graficos["Gráficos de gênero, raça e cargo<br/>fatia das candidaturas x fatia do dinheiro"]
    mapa["Mapa gênero x raça<br/>diferença em pontos percentuais"]
    tabelas["Tabelas do recorte"]
    drill["Detalhar um estado por município"]
    topo --> kpis --> graficos --> mapa --> tabelas --> drill
  end
  lateral -->|"filtra todos os blocos"| principal
```

O que a tela oferece:

* **Seletor de cargo:** todos, vereador, prefeito ou vice-prefeito.
* **Seletor de dinheiro:** receita ou despesa contratada. Indicadores, gráficos e tabelas trocam a série conforme a escolha.
* **Filtros cruzados na barra lateral:** ano (fixo em 2024), região, estado, gênero, raça e faixa etária. Todos valem ao mesmo tempo.
* **Quatro indicadores no topo**, descritos abaixo.
* **Gráficos de gênero, raça e cargo:** barras comparando a fatia das candidaturas (azul) com a fatia do dinheiro (laranja).
* **Mapa gênero x raça:** cada quadrado mostra a diferença, em pontos percentuais, entre a fatia do dinheiro e a fatia das candidaturas daquele grupo. Azul: o grupo recebe mais do que concorre. Vermelho: recebe menos.
* **Tabelas do recorte:** quantidade, valor em reais, os dois percentuais e a diferença em pontos percentuais, por gênero e por raça.
* **Detalhamento por município (drill-down):** ao escolher um estado, uma tabela mostra cada município com a fatia de mulheres nas candidaturas e no dinheiro. Os filtros de gênero, raça e faixa etária continuam valendo, e a tabela ordena por qualquer coluna.
* **Aviso de erro com diagnóstico:** se o banco não responder, o painel mostra o tipo do erro. `RuntimeError` indica que a `DATABASE_URL` não chegou ao painel. `OperationalError` indica que o serviço da Aiven não atendeu.

### Os 4 indicadores

Todos são calculados sobre o recorte escolhido nos seletores e filtros. "Dinheiro" é a receita ou a despesa contratada, conforme o seletor.

|Indicador|O que mede|Como é calculado|Valor no recorte completo (receita)|
|-|-|-|-|
|Candidaturas|Quantas candidaturas entram no recorte|Contagem de linhas de `candidatura`|463.677|
|Receita ou despesa contratada|Quanto dinheiro foi declarado no recorte|Soma de `vr_receita` ou `vr_despesa_contratada` de `financiamento`|R$ 7,04 bilhões|
|Média por candidatura|Quanto cada candidatura movimentou, em média|Dinheiro do recorte dividido pelo número de candidaturas, contando quem declarou zero|R$ 15.187,88|
|Mulheres negras: % do dinheiro|A fatia do dinheiro que foi para mulheres pretas e pardas e a distância até a fatia delas nas candidaturas|Dinheiro de candidaturas com gênero feminino e raça preta ou parda, dividido pelo dinheiro do recorte. A seta mostra essa fatia menos a fatia delas nas candidaturas, em pontos percentuais|11,8% do dinheiro, 5,9 p.p. abaixo dos 17,7% das candidaturas|

O quarto indicador é o central do trabalho: ele junta gênero (ODS 5) e raça (ODS 18) num único número. População negra segue o critério do IBGE, soma de pretos e pardos.

### Implantação do painel

O painel roda no Streamlit Community Cloud, ligado a este repositório no GitHub. Cada commit na `main` atualiza o painel publicado.

1. Em share.streamlit.io, entrar com a conta do GitHub dona do repositório. O Streamlit exige permissão de administrador no repositório para publicar.
2. **Create app**: repositório `Big-Data-TSE`, branch `main`, arquivo principal `dashboard/painel/app.py`, versão padrão do Python (3.12).
3. Em **Advanced settings → Secrets**, uma linha no formato TOML, com aspas retas:

   ```toml
   DATABASE_URL = "postgres://avnadmin:SENHA@HOST:PORTA/defaultdb?sslmode=require"
   ```

   O Streamlit expõe essa chave como variável de ambiente, e o painel a lê do mesmo jeito que lê o `.env` local. A senha nunca entra no repositório.
4. **Deploy.** As dependências vêm do `requirements.txt`.
5. Depois de trocar um Secret, usar **Manage app → Reboot app**. A conexão com o banco fica em cache e só é refeita depois de reiniciar.

Infraestrutura complementar:

* O Streamlit Community Cloud não tem provider de Terraform. A configuração dele fica versionada no próprio repositório: `requirements.txt` (dependências), `.streamlit/config.toml` (configuração do servidor) e `.devcontainer/devcontainer.json` (ambiente de desenvolvimento gerado pelo Streamlit).
* O banco não precisou de mudança no Terraform. O serviço da Aiven já aceita conexão pública com SSL obrigatório, então o Streamlit Cloud se conecta direto.
* O plano gratuito da Aiven desliga o serviço depois de um tempo sem uso, e o app gratuito do Streamlit hiberna. Antes de usar o painel, conferir se o serviço está em Running e, se o painel mostrar a tela de hibernação, clicar para acordá-lo.

## Análise crítica dos resultados (ODS 5 e ODS 18)

A análise mostra que as candidaturas de mulheres e de pessoas negras existem em bom número, mas o dinheiro de campanha não acompanha. A distância cresce de uma etapa para a outra: candidatura, dinheiro e eleição. Valores de receita, recorte completo de 2024.

|Grupo|% das candidaturas|% da receita|Diferença (p.p.)|
|-|-|-|-|
|Homens brancos|30,7|45,6|+14,9|
|Homens pardos|26,8|23,3|−3,5|
|Mulheres brancas|16,1|13,7|−2,4|
|Mulheres pardas|13,5|8,3|−5,2|
|Homens pretos|7,1|4,6|−2,5|
|Mulheres pretas|4,2|3,4|−0,7|

**ODS 5, igualdade de gênero.**

* Mulheres são 34,3% das candidaturas e recebem 25,7% da receita. Em média, uma candidatura feminina declarou R$ 11.390, contra R$ 17.174 de uma masculina.
* A cota de 30% é cumprida no papel: mulheres são 35,4% das candidaturas a vereador. A cota garante a vaga na chapa, mas não garante dinheiro.
* Entre os eleitos, as mulheres caem para 17,9%. Quem recebe menos dinheiro chega menos ao eleitor e se elege menos.

**ODS 18, igualdade étnico-racial.**

* Pessoas brancas são 46,8% das candidaturas e ficam com 59,3% da receita. Pardos (40,3% contra 31,6%) e pretos (11,3% contra 8,1%) recebem menos do que concorrem.
* O único grupo que recebe bem mais do que a sua fatia é o de homens brancos (+14,9 p.p.). O maior prejuízo é o de mulheres pardas (−5,2 p.p.).

**Onde gênero e raça se cruzam.**

* Mulheres negras são 17,7% das candidaturas, recebem 11,8% do dinheiro e são 7,2% dos eleitos. A desigualdade aumenta a cada etapa.
* A média por candidatura de mulheres negras foi de R$ 10.114, contra R$ 16.276 das demais candidaturas.
* A diferença varia muito entre estados. As maiores distâncias para mulheres negras ficaram em Sergipe (−12,0 p.p.), Mato Grosso (−11,3 p.p.) e Espírito Santo (−10,9 p.p.). Roraima (+2,4 p.p.) e Mato Grosso do Sul (+0,3 p.p.) foram exceções.
* O dinheiro também se concentra nos cargos maiores: prefeitos são 3,4% das candidaturas e ficam com 54,9% da receita. Mulheres são só 15,4% das candidaturas a prefeito (35,4% a vereador) e pessoas negras, 35,6% (52,6% a vereador). Essa concentração reforça a desigualdade.

**Limites da análise.**

* A base conta todas as candidaturas registradas, inclusive as indeferidas, porque a situação da candidatura não foi gravada.
* Os valores são os declarados na prestação de contas. Dinheiro não declarado não aparece.
* A análise mostra associação, não causa: receber menos dinheiro e se eleger menos andam juntos, mas outros fatores também pesam no resultado.
* A porcentagem de eleitos vem da coluna de resultado da base (`ds_sit_tot_turno`) e não aparece no painel.

## Escopo e pendências

Fora do desenho, por decisão de escopo:

* OpenSearch, GitHub Actions e série histórica. A base cobre só o pleito municipal de 2024.
* `despesas_pagas`, porque a chave dessa base é `SQ_PRESTADOR_CONTAS` e o join com a candidatura não fecha.

Limitação conhecida: a situação da candidatura não foi gravada na base. Por isso o painel conta todas as candidaturas registradas, inclusive as indeferidas.

O registro completo do que a disciplina pediu e do que foi entregue está em [docs/DOCUMENTO_DO_PROJETO.md](docs/DOCUMENTO_DO_PROJETO.md).

