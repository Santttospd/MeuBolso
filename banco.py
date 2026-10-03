import pandas as pd
import streamlit as st
from sqlalchemy import (
    Column, Date, DateTime, Float, Integer, MetaData, String, Table, delete, func, insert, inspect, select, text, update,
)

# Local: SQLite em arquivo. Na Streamlit Cloud: a URL do PostgreSQL definida
# em [connections.banco] nos Secrets do app.
URL_PADRAO = "sqlite:///meu_bolso.db"

COLUNAS = ["data", "condicao", "banco", "responsavel", "valor", "parcela", "motivo"]

metadata = MetaData()

gastos = Table(
    "gastos",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("usuario", String(50), index=True),
    Column("data", Date, nullable=False),
    Column("condicao", String(20), nullable=False),
    Column("banco", String(50)),
    Column("responsavel", String(50), nullable=False),
    Column("valor", Float, nullable=False),
    Column("parcela", String(10)),
    Column("motivo", String(200)),
)

usuarios = Table(
    "usuarios",
    metadata,
    Column("username", String(50), primary_key=True),
    Column("email", String(200), nullable=False, unique=True),
    Column("first_name", String(100), nullable=False),
    Column("last_name", String(100), nullable=False),
    Column("password", String(200), nullable=False),
    Column("criado_em", DateTime, server_default=func.now()),
)

# Cartões/bancos e responsáveis que cada usuário cadastra para usar nos lançamentos
bancos = Table(
    "bancos",
    metadata,
    Column("usuario", String(50), primary_key=True),
    Column("nome", String(50), primary_key=True),
)

responsaveis = Table(
    "responsaveis",
    metadata,
    Column("usuario", String(50), primary_key=True),
    Column("nome", String(50), primary_key=True),
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
    _migrar(conexao.engine)
    return conexao.engine


def _migrar(engine):
    # Bancos criados antes do cadastro de usuários não têm a coluna "usuario"
    colunas = {coluna["name"] for coluna in inspect(engine).get_columns("gastos")}
    if "usuario" not in colunas:
        with engine.begin() as conexao:
            conexao.execute(text("ALTER TABLE gastos ADD COLUMN usuario VARCHAR(50)"))
            conexao.execute(text("CREATE INDEX IF NOT EXISTS ix_gastos_usuario ON gastos (usuario)"))


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


# ---------- Usuários ----------

def carregar_usuarios():
    """Credenciais no formato do streamlit-authenticator."""
    with _engine().connect() as conexao:
        linhas = conexao.execute(select(usuarios)).mappings().all()
    return {
        "usernames": {
            linha["username"]: {
                "email": linha["email"],
                "first_name": linha["first_name"],
                "last_name": linha["last_name"],
                "password": linha["password"],
            }
            for linha in linhas
        }
    }


def criar_usuario(username, dados):
    with _engine().begin() as conexao:
        conexao.execute(insert(usuarios).values(
            username=username,
            email=dados["email"],
            first_name=dados["first_name"],
            last_name=dados["last_name"],
            password=dados["password"],
        ))
        # A própria pessoa já começa como responsável
        conexao.execute(insert(responsaveis).values(usuario=username, nome=dados["first_name"].strip()[:50]))


def importar_usuarios(credenciais):
    """Copia para o banco os usuários definidos nos Secrets que ainda não existem lá."""
    existentes = carregar_usuarios()["usernames"]
    for username, dados in credenciais.get("usernames", {}).items():
        if username.lower() not in existentes:
            criar_usuario(username.lower(), dados)


# ---------- Gastos ----------
# Todas as funções recebem o usuário logado: cada um só vê e altera os próprios gastos.

def carregar_gastos(usuario):
    consulta = select(*[c for c in gastos.c if c.name != "usuario"]).where(gastos.c.usuario == usuario)
    with _engine().connect() as conexao:
        tabela = pd.read_sql(consulta.order_by(gastos.c.data, gastos.c.id), conexao)
    tabela["data"] = pd.to_datetime(tabela["data"])
    tabela["valor"] = tabela["valor"].astype(float)
    for coluna in ["condicao", "banco", "responsavel", "parcela", "motivo"]:
        tabela[coluna] = tabela[coluna].astype("object")
    return tabela


def inserir_gastos(usuario, df):
    registros = [{**_registro(linha), "usuario": usuario} for linha in df.to_dict("records")]
    if registros:
        with _engine().begin() as conexao:
            conexao.execute(insert(gastos), registros)
    return len(registros)


def atualizar_gasto(usuario, id_gasto, campos):
    valores = {coluna: _limpar(valor) for coluna, valor in campos.items() if coluna in COLUNAS}
    if "data" in valores and valores["data"] is not None:
        valores["data"] = pd.to_datetime(valores["data"]).date()
    if "valor" in valores and valores["valor"] is not None:
        valores["valor"] = float(valores["valor"])
    if valores:
        with _engine().begin() as conexao:
            conexao.execute(
                update(gastos)
                .where(gastos.c.id == int(id_gasto), gastos.c.usuario == usuario)
                .values(**valores)
            )


def excluir_gastos(usuario, ids):
    if ids:
        with _engine().begin() as conexao:
            conexao.execute(
                delete(gastos).where(gastos.c.id.in_([int(i) for i in ids]), gastos.c.usuario == usuario)
            )


def aplicar_alteracoes_editor(usuario, df, alteracoes):
    """Grava no banco o que mudou num st.data_editor exibindo `df`."""
    novas = pd.DataFrame(alteracoes.get("added_rows", []))
    if not novas.empty:
        obrigatorias = novas.reindex(columns=["data", "condicao", "responsavel", "valor"])
        if obrigatorias.isna().any(axis=None):
            raise ValueError("Preencha data, condição, responsável e valor em todas as linhas novas.")

    for posicao, campos in alteracoes.get("edited_rows", {}).items():
        atualizar_gasto(usuario, df.iloc[int(posicao)]["id"], campos)
    excluir_gastos(usuario, [df.iloc[int(posicao)]["id"] for posicao in alteracoes.get("deleted_rows", [])])
    inserir_gastos(usuario, novas)


# ---------- Cadastros do usuário (bancos e responsáveis) ----------

def _listar(tabela, usuario):
    with _engine().connect() as conexao:
        return list(conexao.execute(
            select(tabela.c.nome).where(tabela.c.usuario == usuario).order_by(tabela.c.nome)
        ).scalars())


def _salvar_lista(tabela, usuario, nomes):
    """Substitui a lista do usuário pelos nomes informados (sem vazios nem repetidos)."""
    unicos = {}
    for nome in nomes:
        nome = (_limpar(nome) or "")[:50]
        if nome and nome.casefold() not in unicos:
            unicos[nome.casefold()] = nome
    with _engine().begin() as conexao:
        conexao.execute(delete(tabela).where(tabela.c.usuario == usuario))
        if unicos:
            conexao.execute(insert(tabela), [{"usuario": usuario, "nome": nome} for nome in unicos.values()])
    return sorted(unicos.values())


def listar_bancos(usuario):
    return _listar(bancos, usuario)


def salvar_bancos(usuario, nomes):
    return _salvar_lista(bancos, usuario, nomes)


def listar_responsaveis(usuario):
    return _listar(responsaveis, usuario)


def salvar_responsaveis(usuario, nomes):
    return _salvar_lista(responsaveis, usuario, nomes)
