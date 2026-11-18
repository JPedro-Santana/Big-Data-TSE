# -*- coding: utf-8 -*-
"""Painel local: abre no navegador e lê o PostgreSQL da Aiven.

Uso, na raiz do projeto:
    python -m streamlit run dashboard/painel/app.py
"""

from __future__ import annotations

import os
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parents[2]

ORDEM_GENERO = ["FEMININO", "MASCULINO", "NÃO DIVULGÁVEL"]
ORDEM_RACA = [
    "BRANCA",
    "PARDA",
    "PRETA",
    "AMARELA",
    "INDÍGENA",
    "NÃO INFORMADO",
    "NÃO DIVULGÁVEL",
]
ORDEM_CARGO = ["VEREADOR", "PREFEITO", "VICE-PREFEITO"]
ORDEM_FAIXA = [
    "ATÉ 29 ANOS",
    "30 A 39 ANOS",
    "40 A 49 ANOS",
    "50 A 59 ANOS",
    "60 ANOS OU MAIS",
    "SEM INFORMAÇÃO",
]

# Regiões do IBGE. O DF não entra porque o pleito de 2024 é municipal.
REGIOES = {
    "Norte": ["AC", "AM", "AP", "PA", "RO", "RR", "TO"],
    "Nordeste": ["AL", "BA", "CE", "MA", "PB", "PE", "PI", "RN", "SE"],
    "Centro-Oeste": ["GO", "MS", "MT"],
    "Sudeste": ["ES", "MG", "RJ", "SP"],
    "Sul": ["PR", "RS", "SC"],
}

# População negra segundo o IBGE: pessoas pretas e pardas.
RACA_NEGRA = ["PRETA", "PARDA"]

DINHEIRO = {
    "Receita": "vr_receita",
    "Despesa contratada": "vr_despesa_contratada",
}

CORES = alt.Scale(
    domain=["Candidaturas", "Dinheiro"],
    range=["#4C78A8", "#F58518"],
)


def url_sqlalchemy(url: str) -> str:
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://") :]
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url[len("postgresql://") :]
    return url


def inteiro(valor: float) -> str:
    return f"{int(valor):,}".replace(",", ".")


def reais_curto(valor: float) -> str:
    """Versão curta para caber no card: R$ 7,04 bi, R$ 96,82 mi."""
    for limite, sufixo in ((1e9, "bi"), (1e6, "mi"), (1e3, "mil")):
        if abs(valor) >= limite:
            return f"R$ {valor / limite:.2f}".replace(".", ",") + f" {sufixo}"
    return reais(valor)


def reais(valor: float) -> str:
    texto = f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {texto}"


@st.cache_resource
def conectar():
    load_dotenv(ROOT / ".env")
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        raise RuntimeError("DATABASE_URL ausente")
    return create_engine(url_sqlalchemy(url), pool_pre_ping=True)


@st.cache_data(ttl=300, show_spinner="Lendo o banco...")
def base(cargo: str, coluna_dinheiro: str) -> pd.DataFrame:
    if coluna_dinheiro not in DINHEIRO.values():
        raise ValueError(coluna_dinheiro)
    filtro = ""
    params: dict = {}
    if cargo != "Todos":
        filtro = "WHERE c.ds_cargo = :cargo"
        params["cargo"] = cargo
    # A faixa etária sai pronta do banco. Assim a consulta continua
    # agregada (poucas linhas) e os filtros cruzados rodam na memória.
    sql = f"""
        SELECT c.sg_uf, c.ds_cargo, c.ds_genero, c.ds_cor_raca,
               CASE
                   WHEN c.nr_idade_data_posse IS NULL THEN 'SEM INFORMAÇÃO'
                   WHEN c.nr_idade_data_posse < 30 THEN 'ATÉ 29 ANOS'
                   WHEN c.nr_idade_data_posse < 40 THEN '30 A 39 ANOS'
                   WHEN c.nr_idade_data_posse < 50 THEN '40 A 49 ANOS'
                   WHEN c.nr_idade_data_posse < 60 THEN '50 A 59 ANOS'
                   ELSE '60 ANOS OU MAIS'
               END AS faixa_etaria,
               COUNT(*) AS candidaturas,
               COALESCE(SUM(f.{coluna_dinheiro}), 0) AS dinheiro
        FROM candidatura c
        JOIN financiamento f ON f.sq_candidato = c.sq_candidato
        {filtro}
        GROUP BY c.sg_uf, c.ds_cargo, c.ds_genero, c.ds_cor_raca, faixa_etaria
    """
    with conectar().connect() as conexao:
        return pd.read_sql(text(sql), conexao, params=params)


def opcoes(df: pd.DataFrame, coluna: str, ordem: list[str]) -> list[str]:
    presentes = set(df[coluna].dropna().astype(str))
    return [nome for nome in ordem if nome in presentes] + sorted(presentes - set(ordem))


def filtros_laterais(df: pd.DataFrame) -> dict[str, list[str]]:
    """Filtros cruzados: todos valem juntos. Lista vazia quer dizer 'todos'."""
    st.sidebar.header("Filtros")
    st.sidebar.selectbox(
        "Ano",
        ["2024"],
        disabled=True,
        help="A base tratada cobre só o pleito municipal de 2024.",
    )
    regioes = st.sidebar.multiselect("Região", list(REGIOES), placeholder="Todas")
    ufs_da_regiao = sorted(
        uf for regiao in (regioes or REGIOES) for uf in REGIOES[regiao]
    )
    ufs_disponiveis = [uf for uf in ufs_da_regiao if uf in set(df["sg_uf"].astype(str))]
    ufs = st.sidebar.multiselect("Estado (UF)", ufs_disponiveis, placeholder="Todos")
    generos = st.sidebar.multiselect(
        "Gênero", opcoes(df, "ds_genero", ORDEM_GENERO), placeholder="Todos"
    )
    racas = st.sidebar.multiselect(
        "Raça/cor", opcoes(df, "ds_cor_raca", ORDEM_RACA), placeholder="Todas"
    )
    faixas = st.sidebar.multiselect(
        "Faixa etária", opcoes(df, "faixa_etaria", ORDEM_FAIXA), placeholder="Todas"
    )
    return {
        "sg_uf": ufs or (ufs_da_regiao if regioes else []),
        "ds_genero": generos,
        "ds_cor_raca": racas,
        "faixa_etaria": faixas,
    }


def aplicar_filtros(df: pd.DataFrame, escolhas: dict[str, list[str]]) -> pd.DataFrame:
    saida = df
    for coluna, valores in escolhas.items():
        if valores:
            saida = saida[saida[coluna].astype(str).isin(valores)]
    return saida


def mulheres_negras(df: pd.DataFrame) -> tuple[float, float] | None:
    """Fatia das candidaturas e fatia do dinheiro de mulheres pretas e pardas."""
    alvo = (df["ds_genero"] == "FEMININO") & df["ds_cor_raca"].isin(RACA_NEGRA)
    total_candidaturas = float(df["candidaturas"].sum())
    total_dinheiro = float(df["dinheiro"].sum())
    if not alvo.any() or not total_candidaturas:
        return None
    pct_candidaturas = float(df.loc[alvo, "candidaturas"].sum()) / total_candidaturas * 100
    pct_dinheiro = (
        float(df.loc[alvo, "dinheiro"].sum()) / total_dinheiro * 100 if total_dinheiro else 0.0
    )
    return pct_candidaturas, pct_dinheiro


def comparar(df: pd.DataFrame, coluna: str) -> pd.DataFrame:
    grupo = (
        df.groupby(coluna, dropna=False)
        .agg(candidaturas=("candidaturas", "sum"), dinheiro=("dinheiro", "sum"))
        .reset_index()
    )
    grupo[coluna] = grupo[coluna].astype("string").fillna("SEM INFORMACAO")
    total_candidaturas = float(grupo["candidaturas"].sum())
    total_dinheiro = float(grupo["dinheiro"].sum())
    grupo["pct_candidaturas"] = (
        grupo["candidaturas"] / total_candidaturas * 100 if total_candidaturas else 0
    )
    grupo["pct_dinheiro"] = grupo["dinheiro"] / total_dinheiro * 100 if total_dinheiro else 0
    grupo["diferenca"] = grupo["pct_dinheiro"] - grupo["pct_candidaturas"]
    return grupo


def ordenar(grupo: pd.DataFrame, coluna: str, ordem: list[str]) -> pd.DataFrame:
    rank = {nome: i for i, nome in enumerate(ordem)}
    saida = grupo.copy()
    saida["_ord"] = saida[coluna].map(lambda nome: rank.get(nome, len(ordem)))
    return saida.sort_values(["_ord", coluna]).drop(columns="_ord")


def grafico(grupo: pd.DataFrame, coluna: str, titulo: str) -> alt.Chart:
    longo = grupo.melt(
        id_vars=[coluna],
        value_vars=["pct_candidaturas", "pct_dinheiro"],
        var_name="serie",
        value_name="percentual",
    )
    longo["serie"] = longo["serie"].map(
        {"pct_candidaturas": "Candidaturas", "pct_dinheiro": "Dinheiro"}
    )
    return (
        alt.Chart(longo)
        .mark_bar()
        .encode(
            y=alt.Y(f"{coluna}:N", title=None, sort=list(grupo[coluna])),
            x=alt.X("percentual:Q", title="% do total"),
            color=alt.Color("serie:N", title=None, scale=CORES),
            yOffset="serie:N",
            tooltip=[
                alt.Tooltip(f"{coluna}:N", title="Grupo"),
                alt.Tooltip("serie:N", title="Série"),
                alt.Tooltip("percentual:Q", title="%", format=".1f"),
            ],
        )
        # Altura por barra (Step). Com altura total fixa, o Streamlit espremia
        # o gráfico de gênero e o rótulo MASCULINO sumia por sobreposição.
        .properties(title=titulo, height=alt.Step(20))
    )


def ponto(valor: float, casas: int, sinal: bool = False) -> str:
    texto = f"{valor:+.{casas}f}" if sinal else f"{valor:.{casas}f}"
    return texto.replace(".", ",")


def tabela(grupo: pd.DataFrame, coluna: str, titulo: str, rotulo_dinheiro: str) -> None:
    view = pd.DataFrame(
        {
            titulo: grupo[coluna],
            "Candidaturas": grupo["candidaturas"].map(inteiro),
            rotulo_dinheiro: grupo["dinheiro"].map(reais),
            "% candidaturas": grupo["pct_candidaturas"].map(lambda valor: ponto(valor, 1)),
            "% dinheiro": grupo["pct_dinheiro"].map(lambda valor: ponto(valor, 1)),
            "Diferença (p.p.)": grupo["diferenca"].map(lambda valor: ponto(valor, 1, sinal=True)),
        }
    )
    st.dataframe(view, hide_index=True, width="stretch")


def main() -> None:
    st.set_page_config(
        page_title="Representatividade e financiamento 2024",
        layout="wide",
    )
    st.title("Representatividade política e financiamento eleitoral")
    st.caption(
        "Eleições municipais de 2024. Cada barra compara a fatia das candidaturas "
        "com a fatia do dinheiro declarado. Azul é gente. Laranja é recurso."
    )

    filtro_cargo, filtro_dinheiro = st.columns(2)
    with filtro_cargo:
        cargo = st.selectbox("Cargo", ["Todos", *ORDEM_CARGO])
    with filtro_dinheiro:
        rotulo_dinheiro = st.selectbox("Dinheiro", list(DINHEIRO))

    try:
        df = base(cargo, DINHEIRO[rotulo_dinheiro])
    except Exception:
        st.error(
            "O banco não respondeu. Na Aiven, o serviço precisa estar Running, "
            "e o arquivo .env precisa estar na raiz do projeto."
        )
        st.stop()

    escolhas = filtros_laterais(df)
    df = aplicar_filtros(df, escolhas)

    if df.empty:
        st.warning("Nenhuma candidatura nesse cruzamento de filtros. Tente afrouxar algum filtro.")
        st.stop()

    total_candidaturas = float(df["candidaturas"].sum())
    total_dinheiro = float(df["dinheiro"].sum())
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Candidaturas", inteiro(total_candidaturas))
    m2.metric(rotulo_dinheiro, reais_curto(total_dinheiro), help=f"Valor exato: {reais(total_dinheiro)}")
    m3.metric(
        "Média por candidatura",
        reais(total_dinheiro / total_candidaturas),
        help="Dinheiro do recorte dividido pela quantidade de candidaturas, contando quem declarou zero.",
    )
    fatias = mulheres_negras(df)
    if fatias is None:
        m4.metric(
            "Mulheres negras: % do dinheiro",
            "—",
            help="Não há mulheres pretas ou pardas no recorte filtrado.",
        )
    else:
        pct_candidaturas, pct_dinheiro = fatias
        m4.metric(
            "Mulheres negras: % do dinheiro",
            f"{ponto(pct_dinheiro, 1)}%",
            delta=f"{ponto(pct_dinheiro - pct_candidaturas, 1, sinal=True)} p.p. vs. candidaturas",
            help=(
                f"Mulheres pretas e pardas (população negra, pelo critério do IBGE) são "
                f"{ponto(pct_candidaturas, 1)}% das candidaturas e recebem "
                f"{ponto(pct_dinheiro, 1)}% do dinheiro. Negativo: elas concorrem mais do que recebem."
            ),
        )
    st.caption(f"Recorte com {inteiro(df['sg_uf'].nunique())} UF(s). Use a barra lateral para filtrar.")

    genero = ordenar(comparar(df, "ds_genero"), "ds_genero", ORDEM_GENERO)
    raca = ordenar(comparar(df, "ds_cor_raca"), "ds_cor_raca", ORDEM_RACA)

    st.altair_chart(grafico(genero, "ds_genero", "Gênero"), width="stretch")
    st.altair_chart(grafico(raca, "ds_cor_raca", "Raça"), width="stretch")

    if cargo == "Todos":
        por_cargo = ordenar(comparar(df, "ds_cargo"), "ds_cargo", ORDEM_CARGO)
        st.altair_chart(grafico(por_cargo, "ds_cargo", "Cargo"), width="stretch")
        st.info(
            "Vice-prefeito aparece com quase nenhum dinheiro. "
            "A prestação da chapa costuma ser lançada no candidato a prefeito."
        )

    st.subheader("Números do recorte")
    st.caption(
        "A diferença é a fatia do dinheiro menos a fatia das candidaturas, em pontos percentuais. "
        "Negativo: o grupo concorre mais do que recebe."
    )
    esquerda, direita = st.columns(2)
    with esquerda:
        tabela(genero, "ds_genero", "Gênero", rotulo_dinheiro)
    with direita:
        tabela(raca, "ds_cor_raca", "Raça", rotulo_dinheiro)

    st.caption("Fonte: Portal de Dados Abertos do TSE, eleições 2024. O painel lê o PostgreSQL na Aiven.")


if __name__ == "__main__":
    main()
else:
    main()
