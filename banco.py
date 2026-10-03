import pandas as pd
import streamlit as st
from sqlalchemy import Column, Date, Float, Integer, MetaData, String, Table, delete, insert, select, update

# Local: SQLite em arquivo. Na Streamlit Cloud: a URL do PostgreSQL definida
# em [connections.banco] nos Secrets do app.
URL_PADRAO = "sqlite:///meu_bolso.db"

COLUNAS = ["data", "condicao", "banco", "responsavel", "valor", "parcela", "motivo"]

metadata = MetaData()

gastos = Table(
    "gastos",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("data", Date, nullable=False),
    Column("condicao", String(20), nullable=False),
    Column("banco", String(50)),
    Column("responsavel", String(50), nullable=False),
    Column("valor", Float, nullable=False),
    Column("parcela", String(10)),
    Column("motivo", String(200)),
)

preferencias = Table(
    "preferencias",
    metadata,
    Column("chave", String(50), primary_key=True),
    Column("valor", String(200)),
)


@st.cache_resource
def _engine():
    try:
        tem_secrets = "banco" in st.secrets.get("connections", {})
    except Exception:  # sem arquivo de Secrets
        tem_secrets = False

    if tem_secrets:
        conexao = st.connection("banco", type="sql")
    else:
        conexao = st.connection("banco", type="sql", url=URL_PADRAO)

    metadata.create_all(conexao.engine)
    return conexao.engine


def _limpar(valor):
    if valor is None or (not isinstance(valor, str) and pd.isna(valor)):
        return None
    if isinstance(valor, str):
        valor = valor.strip()
        return valor or None
    return valor


def _registro(linha):
    registro = {coluna: _limpar(linha.get(coluna)) for coluna in COLUNAS}
    if registro["data"] is not None:
        registro["data"] = pd.to_datetime(registro["data"]).date()
    if registro["valor"] is not None:
        registro["valor"] = float(registro["valor"])
    return registro


# ---------- Gastos ----------

def carregar_gastos():
    with _engine().connect() as conexao:
        tabela = pd.read_sql(select(gastos).order_by(gastos.c.data, gastos.c.id), conexao)
    tabela["data"] = pd.to_datetime(tabela["data"])
    tabela["valor"] = tabela["valor"].astype(float)
    for coluna in ["condicao", "banco", "responsavel", "parcela", "motivo"]:
        tabela[coluna] = tabela[coluna].astype("object")
    return tabela


def inserir_gastos(df):
    registros = [_registro(linha) for linha in df.to_dict("records")]
    if registros:
        with _engine().begin() as conexao:
            conexao.execute(insert(gastos), registros)
    return len(registros)


def atualizar_gasto(id_gasto, campos):
    valores = {coluna: _limpar(valor) for coluna, valor in campos.items() if coluna in COLUNAS}
    if "data" in valores and valores["data"] is not None:
        valores["data"] = pd.to_datetime(valores["data"]).date()
    if "valor" in valores and valores["valor"] is not None:
        valores["valor"] = float(valores["valor"])
    if valores:
        with _engine().begin() as conexao:
            conexao.execute(update(gastos).where(gastos.c.id == int(id_gasto)).values(**valores))


def excluir_gastos(ids):
    if ids:
        with _engine().begin() as conexao:
            conexao.execute(delete(gastos).where(gastos.c.id.in_([int(i) for i in ids])))


def aplicar_alteracoes_editor(df, alteracoes):
    """Grava no banco o que mudou num st.data_editor exibindo `df`."""
    novas = pd.DataFrame(alteracoes.get("added_rows", []))
    if not novas.empty:
        obrigatorias = novas.reindex(columns=["data", "condicao", "responsavel", "valor"])
        if obrigatorias.isna().any(axis=None):
            raise ValueError("Preencha data, condição, responsável e valor em todas as linhas novas.")

    for posicao, campos in alteracoes.get("edited_rows", {}).items():
        atualizar_gasto(df.iloc[int(posicao)]["id"], campos)
    excluir_gastos([df.iloc[int(posicao)]["id"] for posicao in alteracoes.get("deleted_rows", [])])
    inserir_gastos(novas)


# ---------- Preferências ----------

def ler_preferencia(chave):
    with _engine().connect() as conexao:
        return conexao.execute(
            select(preferencias.c.valor).where(preferencias.c.chave == chave)
        ).scalar()


def salvar_preferencia(chave, valor):
    with _engine().begin() as conexao:
        alteradas = conexao.execute(
            update(preferencias).where(preferencias.c.chave == chave).values(valor=valor)
        ).rowcount
        if not alteradas:
            conexao.execute(insert(preferencias).values(chave=chave, valor=valor))
