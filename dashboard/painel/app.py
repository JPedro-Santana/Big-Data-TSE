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
RACA_BRANCA = ["BRANCA"]

# KPIs interseccionais: gênero cruzado com raça/cor.
GRUPOS_KPI = [
    ("Mulheres negras", "FEMININO", RACA_NEGRA),
    ("Mulheres brancas", "FEMININO", RACA_BRANCA),
    ("Homens negros", "MASCULINO", RACA_NEGRA),
    ("Homens brancos", "MASCULINO", RACA_BRANCA),
]

METRICAS_GRAFICO = [
    "% do total",
    "Total (R$)",
    "Média por candidatura",
]

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


@st.cache_data(ttl=300, show_spinner="Lendo os municípios...")
def base_municipios(cargo: str, coluna_dinheiro: str, uf: str) -> pd.DataFrame:
    """Mesma agregação da base(), mas por município de uma UF (drill-down)."""
    if coluna_dinheiro not in DINHEIRO.values():
        raise ValueError(coluna_dinheiro)
    filtro = "WHERE c.sg_uf = :uf"
    params: dict = {"uf": uf}
    if cargo != "Todos":
        filtro += " AND c.ds_cargo = :cargo"
        params["cargo"] = cargo
    sql = f"""
        SELECT c.nm_ue, c.ds_genero, c.ds_cor_raca,
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
        GROUP BY c.nm_ue, c.ds_genero, c.ds_cor_raca, faixa_etaria
    """
    with conectar().connect() as conexao:
        return pd.read_sql(text(sql), conexao, params=params)


def opcoes(df: pd.DataFrame, coluna: str, ordem: list[str]) -> list[str]:
    presentes = set(df[coluna].dropna().astype(str))
    return [nome for nome in ordem if nome in presentes] + sorted(presentes - set(ordem))


def filtros_laterais(df: pd.DataFrame) -> dict[str, list[str]]:
    """Filtros cruzados: todos valem juntos. Lista vazia quer dizer 'todos'."""
    st.sidebar.header("Filtros")
    st.sidebar.selectbox("Ano", [2024], disabled=True, help="A base contém apenas as Eleições 2024")
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


def cruzar_genero_raca(df: pd.DataFrame) -> pd.DataFrame:
    """Agrega o recorte por gênero × raça, com fatias e diferença em p.p."""
    total_candidaturas = float(df["candidaturas"].sum())
    total_dinheiro = float(df["dinheiro"].sum())
    grupo = (
        df.groupby(["ds_genero", "ds_cor_raca"], dropna=False)
        .agg(candidaturas=("candidaturas", "sum"), dinheiro=("dinheiro", "sum"))
        .reset_index()
    )
    grupo["ds_genero"] = grupo["ds_genero"].astype("string").fillna("SEM INFORMACAO")
    grupo["ds_cor_raca"] = grupo["ds_cor_raca"].astype("string").fillna("SEM INFORMACAO")
    grupo["pct_candidaturas"] = (
        grupo["candidaturas"] / total_candidaturas * 100 if total_candidaturas else 0.0
    )
    grupo["pct_dinheiro"] = grupo["dinheiro"] / total_dinheiro * 100 if total_dinheiro else 0.0
    grupo["diferenca"] = grupo["pct_dinheiro"] - grupo["pct_candidaturas"]
    return grupo


def fatias_grupo(
    df: pd.DataFrame, genero: str, racas: list[str]
) -> tuple[float, float] | None:
    """Fatia das candidaturas e fatia do dinheiro do cruzamento gênero × raça/cor."""
    if df.empty:
        return None
    total_candidaturas = float(df["candidaturas"].sum())
    if not total_candidaturas:
        return None
    cruzado = cruzar_genero_raca(df)
    alvo = (cruzado["ds_genero"] == genero) & cruzado["ds_cor_raca"].isin(racas)
    if not alvo.any():
        return None
    return (
        float(cruzado.loc[alvo, "pct_candidaturas"].sum()),
        float(cruzado.loc[alvo, "pct_dinheiro"].sum()),
    )


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


def grafico(grupo: pd.DataFrame, coluna: str, titulo: str, metrica: str) -> alt.Chart:
    if metrica == "% do total":
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

    dados = grupo.copy()
    if metrica == "Total (R$)":
        dados["valor"] = dados["dinheiro"].astype(float)
        titulo_eixo = "Total (R$)"
        titulo_tooltip = "Total"
    elif metrica == "Média por candidatura":
        cand = dados["candidaturas"].astype(float)
        dados["valor"] = (dados["dinheiro"].astype(float) / cand).where(cand > 0)
        titulo_eixo = "Média por candidatura (R$)"
        titulo_tooltip = "Média"
    else:
        raise ValueError(metrica)

    dados["rotulo_valor"] = dados["valor"].map(
        lambda valor: reais(float(valor)) if pd.notna(valor) else "—"
    )
    return (
        alt.Chart(dados)
        .mark_bar(color="#F58518")
        .encode(
            y=alt.Y(f"{coluna}:N", title=None, sort=list(dados[coluna])),
            x=alt.X("valor:Q", title=titulo_eixo, axis=alt.Axis(format=",.2f")),
            tooltip=[
                alt.Tooltip(f"{coluna}:N", title="Grupo"),
                alt.Tooltip("rotulo_valor:N", title=titulo_tooltip),
            ],
        )
        .properties(title=titulo, height=alt.Step(20))
    )


def mapa_cruzado(df: pd.DataFrame) -> alt.LayerChart:
    """Gênero × raça: cada quadrado mostra quanto o grupo recebe a mais ou a menos
    do que a sua fatia nas candidaturas (em pontos percentuais)."""
    grupo = cruzar_genero_raca(df)
    # Arredonda antes de escrever, para não aparecer "-0,0" em grupos minúsculos.
    grupo["rotulo"] = grupo["diferenca"].round(1).map(
        lambda valor: "0,0" if valor == 0 else ponto(valor, 1, sinal=True)
    )

    generos = opcoes(grupo, "ds_genero", ORDEM_GENERO)
    racas = opcoes(grupo, "ds_cor_raca", ORDEM_RACA)
    limite = max(float(grupo["diferenca"].abs().max()) if not grupo.empty else 0.0, 0.1)

    base_grafico = alt.Chart(grupo).encode(
        x=alt.X("ds_cor_raca:N", title=None, sort=racas, axis=alt.Axis(labelAngle=0)),
        y=alt.Y("ds_genero:N", title=None, sort=generos),
    )
    quadrados = base_grafico.mark_rect().encode(
        color=alt.Color(
            "diferenca:Q",
            title="Diferença (p.p.)",
            scale=alt.Scale(scheme="redblue", domain=[-limite, limite]),
        ),
        tooltip=[
            alt.Tooltip("ds_genero:N", title="Gênero"),
            alt.Tooltip("ds_cor_raca:N", title="Raça"),
            alt.Tooltip("pct_candidaturas:Q", title="% candidaturas", format=".1f"),
            alt.Tooltip("pct_dinheiro:Q", title="% dinheiro", format=".1f"),
            alt.Tooltip("diferenca:Q", title="Diferença (p.p.)", format="+.1f"),
        ],
    )
    numeros = base_grafico.mark_text(fontSize=13).encode(text="rotulo:N")
    return (quadrados + numeros).properties(
        title="Gênero × raça: dinheiro menos candidaturas (p.p.)",
        height=alt.Step(46),
    )


def tabela_municipios(df: pd.DataFrame, rotulo_dinheiro: str) -> pd.DataFrame:
    """Uma linha por município, com a fatia de mulheres nas candidaturas e no dinheiro."""
    mulher = df["ds_genero"] == "FEMININO"
    por_municipio = df.assign(
        cand_mulheres=df["candidaturas"].where(mulher, 0),
        dinheiro_mulheres=df["dinheiro"].where(mulher, 0),
    ).groupby("nm_ue", dropna=False)[
        ["candidaturas", "dinheiro", "cand_mulheres", "dinheiro_mulheres"]
    ].sum()
    por_municipio = por_municipio[por_municipio["candidaturas"] > 0]
    pct_cand = por_municipio["cand_mulheres"] / por_municipio["candidaturas"] * 100
    pct_din = (
        por_municipio["dinheiro_mulheres"]
        / por_municipio["dinheiro"].where(por_municipio["dinheiro"] > 0)
        * 100
    )
    saida = pd.DataFrame(
        {
            "Município": por_municipio.index.astype(str),
            "Candidaturas": por_municipio["candidaturas"].astype(int),
            f"{rotulo_dinheiro} (R$)": por_municipio["dinheiro"].astype(float).round(2),
            "Mulheres: % candidaturas": pct_cand.round(1),
            "Mulheres: % dinheiro": pct_din.round(1),
            "Diferença (p.p.)": (pct_din - pct_cand).round(1),
        }
    )
    return saida.sort_values("Candidaturas", ascending=False)


def detalhar_municipios(
    cargo: str, rotulo_dinheiro: str, ufs_no_recorte: list[str], escolhas: dict[str, list[str]]
) -> None:
    st.subheader("Detalhar um estado por município")
    st.caption(
        "Escolha um estado para descer do nível estadual para os municípios. "
        "Os filtros da barra lateral (gênero, raça e faixa etária) continuam valendo."
    )
    uf = st.selectbox("Estado", ["—", *ufs_no_recorte], key="drill_uf")
    if uf == "—":
        return
    try:
        municipios = base_municipios(cargo, DINHEIRO[rotulo_dinheiro], uf)
    except Exception:
        st.error("Não foi possível ler os municípios desse estado agora.")
        return
    sem_uf = {coluna: valores for coluna, valores in escolhas.items() if coluna != "sg_uf"}
    municipios = aplicar_filtros(municipios, sem_uf)
    if municipios.empty:
        st.warning("Nenhuma candidatura nesse estado com os filtros atuais.")
        return
    tabela = tabela_municipios(municipios, rotulo_dinheiro)
    st.caption(
        f"{inteiro(len(tabela))} município(s) em {uf}. Diferença negativa: as mulheres "
        "concorrem mais do que recebem naquele município. Clique no título de uma coluna para ordenar."
    )
    st.dataframe(
        tabela,
        hide_index=True,
        width="stretch",
        # "localized" usa o formato do navegador (no Brasil: 1.234.567,89) e
        # mantém os números como números, então a ordenação por coluna funciona.
        column_config={
            coluna: st.column_config.NumberColumn(format="localized")
            for coluna in tabela.columns
            if coluna != "Município"
        },
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

    filtro_cargo, filtro_dinheiro, filtro_metrica = st.columns(3)
    with filtro_cargo:
        cargo = st.selectbox("Cargo", ["Todos", *ORDEM_CARGO])
    with filtro_dinheiro:
        rotulo_dinheiro = st.selectbox("Dinheiro", list(DINHEIRO))
    with filtro_metrica:
        metrica_grafico = st.selectbox("Métrica do gráfico", METRICAS_GRAFICO)

    try:
        df = base(cargo, DINHEIRO[rotulo_dinheiro])
    except Exception as erro:
        st.error(
            "O banco não respondeu. Na Aiven, o serviço precisa estar Running, "
            "e o arquivo .env precisa estar na raiz do projeto."
        )
        # Só o tipo do erro, nunca a mensagem (que pode trazer o endereço do banco).
        # RuntimeError: DATABASE_URL não chegou ao painel (.env ou Secrets).
        # OperationalError: o banco não atendeu (serviço desligado na Aiven).
        st.caption(f"Detalhe técnico: {type(erro).__name__}")
        st.stop()

    escolhas = filtros_laterais(df)
    df = aplicar_filtros(df, escolhas)

    if df.empty:
        st.warning("Nenhuma candidatura nesse cruzamento de filtros. Tente afrouxar algum filtro.")
        st.stop()

    total_candidaturas = float(df["candidaturas"].sum())
    total_dinheiro = float(df["dinheiro"].sum())
    cards = st.columns(4)
    for card, (rotulo, genero, racas) in zip(cards, GRUPOS_KPI):
        fatias = fatias_grupo(df, genero, racas)
        if fatias is None:
            card.metric(
                f"{rotulo}: % do dinheiro",
                "—",
                help="Não há candidaturas desse cruzamento no recorte filtrado.",
            )
        else:
            pct_candidaturas, pct_dinheiro = fatias
            card.metric(
                f"{rotulo}: % do dinheiro",
                f"{ponto(pct_dinheiro, 1)}%",
                delta=f"{ponto(pct_dinheiro - pct_candidaturas, 1, sinal=True)} p.p. vs. candidaturas",
                help=(
                    f"{rotulo} são {ponto(pct_candidaturas, 1)}% das candidaturas e recebem "
                    f"{ponto(pct_dinheiro, 1)}% do dinheiro. Negativo: o grupo concorre mais do que recebe."
                ),
            )
    st.caption(
        f"Recorte com {inteiro(total_candidaturas)} candidaturas e {reais(total_dinheiro)} "
        f"em {rotulo_dinheiro.lower()} ({inteiro(df['sg_uf'].nunique())} UF(s)). "
        "Use a barra lateral para filtrar."
    )

    genero = ordenar(comparar(df, "ds_genero"), "ds_genero", ORDEM_GENERO)
    raca = ordenar(comparar(df, "ds_cor_raca"), "ds_cor_raca", ORDEM_RACA)

    st.altair_chart(grafico(genero, "ds_genero", "Gênero", metrica_grafico), width="stretch")
    st.altair_chart(grafico(raca, "ds_cor_raca", "Raça", metrica_grafico), width="stretch")
    st.altair_chart(mapa_cruzado(df), width="stretch")
    st.caption(
        "Azul: o grupo recebe uma fatia do dinheiro maior que a sua fatia nas candidaturas. "
        "Vermelho: recebe menos. Passe o mouse num quadrado para ver as duas porcentagens."
    )

    if cargo == "Todos":
        por_cargo = ordenar(comparar(df, "ds_cargo"), "ds_cargo", ORDEM_CARGO)
        st.altair_chart(grafico(por_cargo, "ds_cargo", "Cargo", metrica_grafico), width="stretch")
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

    ufs_no_recorte = sorted(df["sg_uf"].dropna().astype(str).unique())
    detalhar_municipios(cargo, rotulo_dinheiro, ufs_no_recorte, escolhas)

    st.caption("Fonte: Portal de Dados Abertos do TSE, eleições 2024. O painel lê o PostgreSQL na Aiven.")


if __name__ == "__main__":
    main()
else:
    main()
