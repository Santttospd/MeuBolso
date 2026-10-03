import html
import pandas as pd
import streamlit as st
import plotly.express as px
import streamlit_antd_components as sac
from banco import (
    aplicar_alteracoes_editor, carregar_gastos, inserir_gastos,
    listar_bancos, listar_responsaveis, salvar_bancos, salvar_responsaveis,
)
from importar_fatura import FaturaInvalida, ler_fatura
from autenticacao import autenticar

st.set_page_config(
    page_title="Meu Bolso",
    page_icon="💰",
    layout="wide",
)


# ---------- Constantes ----------

CONDICOES = ["Cartão", "Avulso"]
CORES = ["#22C55E", "#38BDF8", "#A78BFA", "#F59E0B", "#F43F5E", "#14B8A6"]


# ---------- Funções auxiliares ----------

def formatar_brl(valor):
    texto = f"{valor:,.2f}"
    return "R$ " + texto.replace(",", "X").replace(".", ",").replace("X", ".")


def usuario_logado():
    return st.session_state["username"]


def opcoes(cadastrados, usados):
    # Mantém válidos os valores antigos que saíram do cadastro
    return sorted(set(cadastrados) | set(usados.dropna()))


def pedir_cadastro(o_que):
    st.info(f"Para continuar, cadastre {o_que} em **Meus cadastros**, no menu.", icon=":material/info:")


def avisar(mensagem):
    # Guarda o aviso para mostrar depois do st.rerun()
    st.session_state["aviso"] = mensagem
    st.rerun()


def mostrar_aviso_pendente():
    if "aviso" in st.session_state:
        st.toast(st.session_state.pop("aviso"), icon="✅")


def sem_lancamentos(tabela):
    if not tabela.empty:
        return False
    st.info(
        "Ainda não há lançamentos. Comece pelo **Lançamento Manual** ou **Importar fatura** no menu.",
        icon=":material/info:",
    )
    return True


def cabecalho(titulo, descricao):
    st.title(titulo)
    st.caption(descricao)


def mostrar_kpis(tabela):
    k1, k2, k3 = st.columns(3)
    k1.metric("Total gasto", formatar_brl(tabela["valor"].sum()), border=True)
    k2.metric("Lançamentos", len(tabela), border=True)
    k3.metric("Maior gasto", formatar_brl(tabela["valor"].max()), border=True)


def estilizar_grafico(fig):
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(t=20, b=20, l=20, r=20),
        font=dict(size=14),
    )
    return fig


def estilizar_sidebar():
    # Cores derivadas da cor do texto (currentColor): funcionam no tema claro e no escuro
    st.markdown("""
    <style>
    section[data-testid="stSidebar"] {
        border-right: 1px solid color-mix(in srgb, currentColor 12%, transparent);
    }
    section[data-testid="stSidebar"] [data-testid="stSidebarUserContent"] { padding-top: 0; }
    .sidebar-marca { display: flex; align-items: center; gap: 0.75rem; margin-bottom: 1.25rem; }
    .sidebar-marca .icone {
        font-size: 1.6rem; width: 2.75rem; height: 2.75rem;
        display: flex; align-items: center; justify-content: center;
        background-color: rgba(34, 197, 94, 0.15); border-radius: 12px;
    }
    .sidebar-marca .nome { font-size: 1.25rem; font-weight: 700; line-height: 1.2; }
    .sidebar-marca .sub, .sidebar-rotulo, .usuario .sub, .dica-tema { opacity: 0.65; }
    .sidebar-marca .sub { font-size: 0.8rem; }
    .sidebar-rotulo {
        font-size: 0.7rem; font-weight: 600; letter-spacing: 0.08em;
        text-transform: uppercase; margin: 0 0 0.25rem;
    }

    /* Rodapé fixo no fim da barra lateral */
    .st-key-rodape-sidebar {
        position: fixed;
        bottom: 1rem;
        width: calc(var(--sidebar-width, 18rem) - 3rem);
        padding-top: 1rem;
        border-top: 1px solid color-mix(in srgb, currentColor 12%, transparent);
    }
    .usuario { display: flex; align-items: center; gap: 0.6rem; margin-bottom: 0.5rem; }
    .usuario .avatar {
        width: 2.25rem; height: 2.25rem; border-radius: 50%;
        display: flex; align-items: center; justify-content: center;
        background-color: #16A34A; color: #FFFFFF; font-weight: 700;
    }
    .usuario .nome { font-weight: 600; line-height: 1.2; }
    .usuario .sub { font-size: 0.75rem; }
    .st-key-rodape-sidebar p.dica-tema { font-size: 0.75rem; margin: 0 0 0.5rem; }
    </style>
    """, unsafe_allow_html=True)


def montar_sidebar(authenticator):
    with st.sidebar:
        estilizar_sidebar()
        st.markdown(
            "<div class='sidebar-marca'>"
            "<div class='icone'>💰</div>"
            "<div><div class='nome'>Meu Bolso</div><div class='sub'>Controle de gastos</div></div>"
            "</div>",
            unsafe_allow_html=True,
        )

        st.markdown("<p class='sidebar-rotulo'>Menu</p>", unsafe_allow_html=True)
        menu = sac.menu([
            sac.MenuItem("Lançamentos", icon="table", children=[
                sac.MenuItem("Lançamento Manual", icon="plus-circle"),
                sac.MenuItem("Importar fatura", icon="file-earmark-arrow-up"),
                sac.MenuItem("Histórico", icon="list-ul"),
            ]),
            sac.MenuItem("Análises", icon="bar-chart", children=[
                sac.MenuItem("Por mês", icon="calendar3"),
                sac.MenuItem("Por banco", icon="bank"),
            ]),
            sac.MenuItem("Meus cadastros", icon="gear"),
        ], variant="left-bar", color="green", open_all=True, index=1)

        with st.container(key="rodape-sidebar"):
            nome = st.session_state.get("name") or "Usuário"
            st.markdown(
                "<div class='usuario'>"
                f"<div class='avatar'>{html.escape(nome[0].upper())}</div>"
                f"<div><div class='nome'>{html.escape(nome)}</div><div class='sub'>Conectado</div></div>"
                "</div>",
                unsafe_allow_html=True,
            )

            st.markdown(
                "<p class='dica-tema'>🎨 Tema claro/escuro: menu ⋮ no topo da página</p>",
                unsafe_allow_html=True,
            )

            authenticator.logout("Sair", "main", key="botao-sair", use_container_width=True)

    return menu


# ---------- Páginas ----------

def pagina_lancamento_manual():
    cabecalho("Lançamento Manual", "Registre um gasto de cartão ou um gasto avulso, como água e internet.")

    bancos = listar_bancos(usuario_logado())
    responsaveis = listar_responsaveis(usuario_logado())
    if not responsaveis:
        pedir_cadastro("pelo menos um responsável")
        return

    condicao = st.segmented_control("Condição", CONDICOES, default="Cartão", required=True)
    avulso = condicao == "Avulso"
    if not avulso and not bancos:
        pedir_cadastro("um cartão ou banco para lançar gastos de cartão")
        return

    with st.form("lancamento", clear_on_submit=True, border=True):
        c1, c2, c3 = st.columns(3)
        data = c1.date_input("Data", format="DD/MM/YYYY")
        if avulso:
            banco = None
            motivo = c2.text_input("Motivo", placeholder="Ex.: Água, Internet, Luz")
        else:
            banco = c2.selectbox("Banco", bancos)
            motivo = None
        responsavel = c3.selectbox("Responsável", responsaveis)

        c4, c5, _ = st.columns(3)
        valor = c4.number_input("Valor (R$)", min_value=0.0, format="%.2f")
        parcelas = c5.number_input("Nº de parcelas", min_value=1, max_value=12, step=1)

        salvar = st.form_submit_button("Salvar lançamento", icon=":material/save:", type="primary")

    if salvar:
        if avulso and not motivo.strip():
            st.error("Informe o motivo do gasto avulso.")
            return

        df = pd.DataFrame([{
            "data": data,
            "condicao": condicao,
            "banco": banco,
            "responsavel": responsavel,
            "valor": valor,
            "parcela": f"1/{parcelas}",
            "motivo": motivo.strip() if avulso else None,
        }])
        inserir_gastos(usuario_logado(), df)
        st.toast("Lançamento salvo com sucesso!", icon="✅")


def pagina_importar_fatura():
    cabecalho("Importar Fatura", "Envie o PDF da fatura do cartão para importar as compras automaticamente.")

    bancos = listar_bancos(usuario_logado())
    responsaveis = listar_responsaveis(usuario_logado())
    if not bancos or not responsaveis:
        pedir_cadastro("um cartão/banco e um responsável")
        return

    c1, c2 = st.columns(2)
    banco = c1.selectbox("Banco do cartão", bancos)
    responsavel = c2.selectbox("Responsável pelas compras", responsaveis)
    st.caption("Por enquanto, a leitura automática funciona com faturas do Mercado Pago.")

    arquivo = st.file_uploader("Arquivo PDF da fatura", type="pdf")
    if arquivo is None:
        return

    if arquivo.file_id in st.session_state.get("faturas_importadas", set()):
        st.info("Esta fatura já foi importada. Envie outro arquivo para importar mais compras.", icon=":material/info:")
        return

    try:
        df = ler_fatura(arquivo, banco=banco, responsavel=responsavel)
    except FaturaInvalida as erro:
        st.error(str(erro), icon=":material/error:")
        return

    st.write(f"**{len(df)} compras encontradas** — total de {formatar_brl(df['valor'].sum())}")
    st.dataframe(
        df,
        hide_index=True,
        width="stretch",
        column_config={
            "valor": st.column_config.NumberColumn("Valor", format="R$ %.2f"),
        },
    )

    if st.button("Confirmar importação", icon=":material/upload:", type="primary"):
        inserir_gastos(usuario_logado(), df)
        st.session_state.setdefault("faturas_importadas", set()).add(arquivo.file_id)
        avisar(f"{len(df)} compras importadas com sucesso!")


def pagina_historico():
    cabecalho("Histórico de Lançamentos", "Edite os lançamentos diretamente na tabela e clique em salvar.")

    df = carregar_gastos(usuario_logado())
    if df.empty:
        st.caption("Nenhum lançamento ainda. Você pode adicionar linhas direto na tabela.")

    # A chave muda depois de salvar, para o editor recomeçar sem alterações pendentes
    chave = f"editor_historico_{st.session_state.get('versao_historico', 0)}"
    st.data_editor(
        df,
        key=chave,
        hide_index=True,
        width="stretch",
        num_rows="dynamic",
        column_config={
            "id": None,
            "data": st.column_config.DateColumn("Data", format="DD/MM/YYYY"),
            "condicao": st.column_config.SelectboxColumn("Condição", options=CONDICOES),
            "banco": st.column_config.SelectboxColumn(
                "Banco", options=opcoes(listar_bancos(usuario_logado()), df["banco"])
            ),
            "responsavel": st.column_config.SelectboxColumn(
                "Responsável", options=opcoes(listar_responsaveis(usuario_logado()), df["responsavel"])
            ),
            "valor": st.column_config.NumberColumn("Valor", format="R$ %.2f", min_value=0.0),
            "parcela": st.column_config.TextColumn("Parcela"),
            "motivo": st.column_config.TextColumn("Motivo"),
        },
    )

    if st.button("Salvar alterações", icon=":material/save:", type="primary"):
        try:
            aplicar_alteracoes_editor(usuario_logado(), df, st.session_state[chave])
        except ValueError as erro:
            st.error(str(erro))
            return

        st.session_state["versao_historico"] = st.session_state.get("versao_historico", 0) + 1
        avisar("Alterações salvas!")


def pagina_por_mes():
    cabecalho("Análise por Mês", "Total de gastos em cada mês, dividido por responsável.")

    tabela = carregar_gastos(usuario_logado())
    if sem_lancamentos(tabela):
        return

    mostrar_kpis(tabela)
    st.divider()

    tabela["mes"] = tabela["data"].dt.to_period("M")
    tabela_mes = tabela.groupby(["mes", "responsavel"])["valor"].sum().reset_index().sort_values("mes")
    tabela_mes["mes"] = tabela_mes["mes"].dt.strftime("%m/%Y")
    fig = px.bar(
        tabela_mes,
        x="mes",
        y="valor",
        color="responsavel",
        text_auto=".2f",
        color_discrete_sequence=CORES,
        category_orders={"mes": list(dict.fromkeys(tabela_mes["mes"]))},
        labels={"mes": "Mês", "valor": "Valor (R$)", "responsavel": "Responsável"},
    )
    st.plotly_chart(estilizar_grafico(fig), width="stretch")


def pagina_por_banco():
    cabecalho("Análise por Banco", "Como os gastos se distribuem entre os bancos. Gastos avulsos aparecem como \"Avulso\".")

    tabela = carregar_gastos(usuario_logado())
    if sem_lancamentos(tabela):
        return

    mostrar_kpis(tabela)
    st.divider()

    tabela["banco"] = tabela["banco"].fillna("Avulso")
    tabela_banco = tabela.groupby(["banco"])["valor"].sum().reset_index()
    fig = px.pie(
        tabela_banco,
        names="banco",
        values="valor",
        hole=0.5,
        color_discrete_sequence=CORES,
        labels={"banco": "Banco", "valor": "Valor (R$)"},
    )
    fig.update_traces(textinfo="percent+label")
    st.plotly_chart(estilizar_grafico(fig), width="stretch")


def editar_lista(titulo, chave, listar, salvar, dica):
    usuario = usuario_logado()
    with st.container(border=True):
        st.subheader(titulo)
        st.caption(dica)
        versao = st.session_state.get(f"versao_{chave}", 0)
        editado = st.data_editor(
            pd.DataFrame({"nome": listar(usuario)}, dtype="object"),
            key=f"editor_{chave}_{versao}",
            num_rows="dynamic",
            hide_index=True,
            width="stretch",
            column_config={"nome": st.column_config.TextColumn("Nome", max_chars=50, required=True)},
        )
        if st.button("Salvar", key=f"salvar_{chave}", icon=":material/save:", type="primary"):
            salvos = salvar(usuario, editado["nome"].tolist())
            st.session_state[f"versao_{chave}"] = versao + 1
            avisar(f"{titulo}: {len(salvos)} item(ns) salvo(s).")


def pagina_cadastros():
    cabecalho("Meus cadastros", "Cadastre seus cartões/bancos e as pessoas responsáveis pelos gastos.")

    c1, c2 = st.columns(2)
    with c1:
        editar_lista(
            "Cartões e bancos", "bancos", listar_bancos, salvar_bancos,
            "Ex.: Nubank, Inter, Mercado Pago. Use + para adicionar e a lixeira para remover.",
        )
    with c2:
        editar_lista(
            "Responsáveis", "responsaveis", listar_responsaveis, salvar_responsaveis,
            "Quem fez cada gasto. Ex.: você, cônjuge, filhos.",
        )
    st.caption("Remover um item não altera os lançamentos antigos que já o usam.")


PAGINAS = {
    "Lançamento Manual": pagina_lancamento_manual,
    "Importar fatura": pagina_importar_fatura,
    "Histórico": pagina_historico,
    "Por mês": pagina_por_mes,
    "Por banco": pagina_por_banco,
    "Meus cadastros": pagina_cadastros,
}


# ---------- Execução do app ----------

authenticator = autenticar()
menu = montar_sidebar(authenticator)
mostrar_aviso_pendente()

if menu in PAGINAS:
    PAGINAS[menu]()
