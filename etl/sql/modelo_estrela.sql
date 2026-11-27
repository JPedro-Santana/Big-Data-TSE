-- Modelo estrela sobre as tabelas da carga (candidatura e financiamento).
--
-- São só views: não copiam nem alteram dados, e a carga (etl/03_load.py)
-- continua igual. As chaves das dimensões são substitutas, geradas com
-- DENSE_RANK sobre os atributos naturais, e a fato liga cada candidatura
-- às dimensões pelos mesmos atributos.
--
-- Execução (psql ou qualquer cliente conectado ao DATABASE_URL):
--   psql "$DATABASE_URL" -f etl/sql/modelo_estrela.sql
--
-- Observação: a carga (etl/carregar.py) apaga estas views antes de recriar
-- as tabelas de origem. Depois de uma nova carga, rode este script de novo.

BEGIN;

-- Dimensão local: UF, município e região (regiões do IBGE).
CREATE OR REPLACE VIEW dim_local AS
SELECT
    DENSE_RANK() OVER (ORDER BY l.sg_uf, l.nm_ue)::INTEGER AS id_local,
    l.sg_uf,
    l.nm_ue AS nm_municipio,
    CASE
        WHEN l.sg_uf IN ('AC','AM','AP','PA','RO','RR','TO') THEN 'NORTE'
        WHEN l.sg_uf IN ('AL','BA','CE','MA','PB','PE','PI','RN','SE') THEN 'NORDESTE'
        WHEN l.sg_uf IN ('DF','GO','MS','MT') THEN 'CENTRO-OESTE'
        WHEN l.sg_uf IN ('ES','MG','RJ','SP') THEN 'SUDESTE'
        WHEN l.sg_uf IN ('PR','RS','SC') THEN 'SUL'
    END AS nm_regiao
FROM (SELECT DISTINCT sg_uf, nm_ue FROM candidatura) AS l;

-- Dimensão partido: sigla e nome.
CREATE OR REPLACE VIEW dim_partido AS
SELECT
    DENSE_RANK() OVER (ORDER BY p.sg_partido, p.nm_partido)::INTEGER AS id_partido,
    p.sg_partido,
    p.nm_partido
FROM (SELECT DISTINCT sg_partido, nm_partido FROM candidatura) AS p;

-- Dimensão cargo: vereador, prefeito, vice-prefeito.
CREATE OR REPLACE VIEW dim_cargo AS
SELECT
    DENSE_RANK() OVER (ORDER BY c.ds_cargo)::INTEGER AS id_cargo,
    c.ds_cargo
FROM (SELECT DISTINCT ds_cargo FROM candidatura) AS c;

-- Dimensão perfil: gênero, raça/cor e faixa etária (mesmas faixas do painel).
CREATE OR REPLACE VIEW dim_perfil AS
SELECT
    DENSE_RANK() OVER (ORDER BY p.ds_genero, p.ds_cor_raca, p.ds_faixa_etaria)::INTEGER AS id_perfil,
    p.ds_genero,
    p.ds_cor_raca,
    p.ds_faixa_etaria
FROM (
    SELECT DISTINCT
        ds_genero,
        ds_cor_raca,
        CASE
            WHEN nr_idade_data_posse IS NULL THEN 'SEM INFORMAÇÃO'
            WHEN nr_idade_data_posse < 30 THEN 'ATÉ 29 ANOS'
            WHEN nr_idade_data_posse < 40 THEN '30 A 39 ANOS'
            WHEN nr_idade_data_posse < 50 THEN '40 A 49 ANOS'
            WHEN nr_idade_data_posse < 60 THEN '50 A 59 ANOS'
            ELSE '60 ANOS OU MAIS'
        END AS ds_faixa_etaria
    FROM candidatura
) AS p;

-- Fato: uma linha por candidatura, com as chaves das dimensões e as medidas.
-- As chaves são calculadas com o mesmo DENSE_RANK de cada dimensão (em vez de
-- JOIN com IS NOT DISTINCT FROM, que impede hash join e fica muito lento).
CREATE OR REPLACE VIEW fato_candidatura AS
WITH base AS (
    SELECT
        c.sq_candidato,
        c.ano_eleicao,
        c.sg_uf,
        c.nm_ue,
        c.sg_partido,
        c.nm_partido,
        c.ds_cargo,
        c.ds_genero,
        c.ds_cor_raca,
        CASE
            WHEN c.nr_idade_data_posse IS NULL THEN 'SEM INFORMAÇÃO'
            WHEN c.nr_idade_data_posse < 30 THEN 'ATÉ 29 ANOS'
            WHEN c.nr_idade_data_posse < 40 THEN '30 A 39 ANOS'
            WHEN c.nr_idade_data_posse < 50 THEN '40 A 49 ANOS'
            WHEN c.nr_idade_data_posse < 60 THEN '50 A 59 ANOS'
            ELSE '60 ANOS OU MAIS'
        END AS ds_faixa_etaria,
        c.ds_sit_tot_turno,
        c.nr_turno_resultado
    FROM candidatura c
),
chaves AS (
    -- Mesmos DENSE_RANK das dimensões, sobre a mesma tabela, os mesmos
    -- atributos e na mesma ordem: os ids saem iguais aos das dims sem JOIN.
    SELECT
        b.*,
        DENSE_RANK() OVER (ORDER BY b.sg_uf, b.nm_ue)::INTEGER AS id_local,
        DENSE_RANK() OVER (ORDER BY b.sg_partido, b.nm_partido)::INTEGER AS id_partido,
        DENSE_RANK() OVER (ORDER BY b.ds_cargo)::INTEGER AS id_cargo,
        DENSE_RANK() OVER (ORDER BY b.ds_genero, b.ds_cor_raca, b.ds_faixa_etaria)::INTEGER AS id_perfil
    FROM base b
)
SELECT
    k.sq_candidato,
    k.id_local,
    k.id_partido,
    k.id_cargo,
    k.id_perfil,
    k.ano_eleicao,
    k.ds_sit_tot_turno,
    k.nr_turno_resultado,
    1 AS qt_candidaturas,
    f.vr_receita,
    f.vr_despesa_contratada,
    f.qt_receitas,
    f.qt_despesas
FROM chaves k
JOIN financiamento f ON f.sq_candidato = k.sq_candidato;

COMMIT;
