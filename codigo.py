import html
import pandas as pd
import streamlit as st
import plotly.express as px
import streamlit_antd_components as sac
from banco import aplicar_alteracoes_editor, carregar_gastos, inserir_gastos
from importar_fatura import FaturaInvalida, ler_fatura
from autenticacao import autenticar
from tema import aplicar_tema_salvo, cores, tema_atual, trocar_tema

st.set_page_config(
    page_title="Meu Bolso",
    page_icon="💰",
    layout="wide",
)
aplicar_tema_salvo()


# ---------- Constantes ----------

RESPONSAVEIS = ["Pedro", "Amor", "Mãe", "Sogra", "Ryan"]
BANCOS = ["Mercado Pago", "Inter", "Nubank"]
CONDICOES = ["Cartão", "Avulso"]
CORES = ["#22C55E", "#38BDF8", "#A78BFA", "#F59E0B", "#F43F5E", "#14B8A6"]


# ---------- Funções auxiliares ----------

def formatar_brl(valor):
    texto = f"{valor:,.2f}"
    return "R$ " + texto.replace(",", "X").replace(".", ",").replace("X", ".")


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
        template=cores()["plotly"],
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(t=20, b=20, l=20, r=20),
        font=dict(size=14),
    )
    return fig


def estilizar_sidebar():
    c = cores()
    st.markdown(f"""
    <style>
    section[data-testid="stSidebar"] {{
        border-right: 1px solid {c["borda"]};
    }}
    section[data-testid="stSidebar"] [data-testid="stSidebarUserContent"] {{
        padding-top: 0;
    }}
    .sidebar-marca {{ display: flex; align-items: center; gap: 0.75rem; margin-bottom: 1.25rem; }}
    .sidebar-marca .icone {{
        font-size: 1.6rem; width: 2.75rem; height: 2.75rem;
        display: flex; align-items: center; justify-content: center;
        background-color: {c["primaryColor"]}22; border-radius: 12px;
    }}
    .sidebar-marca .nome {{ font-size: 1.25rem; font-weight: 700; line-height: 1.2; }}
    .sidebar-marca .sub {{ font-size: 0.8rem; color: {c["texto_suave"]}; }}
    .sidebar-rotulo {{
        font-size: 0.7rem; font-weight: 600; letter-spacing: 0.08em;
        text-transform: uppercase; color: {c["texto_suave"]}; margin: 0 0 0.25rem;
    }}

    /* Rodapé fixo no fim da barra lateral */
    .st-key-rodape-sidebar {{
        position: fixed;
        bottom: 1rem;
        width: calc(var(--sidebar-width, 18rem) - 3rem);
        padding-top: 1rem;
        border-top: 1px solid {c["borda"]};
    }}
    .usuario {{ display: flex; align-items: center; gap: 0.6rem; margin-bottom: 0.5rem; }}
    .usuario .avatar {{
        width: 2.25rem; height: 2.25rem; border-radius: 50%;
        display: flex; align-items: center; justify-content: center;
        background-color: {c["primaryColor"]}; color: #FFFFFF; font-weight: 700;
    }}
    .usuario .nome {{ font-weight: 600; line-height: 1.2; }}
    .usuario .sub {{ font-size: 0.75rem; color: {c["texto_suave"]}; }}
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

            escuro = st.toggle("Tema escuro", value=tema_atual() == "dark")
            if escuro != (tema_atual() == "dark"):
                trocar_tema("dark" if escuro else "light")

            authenticator.logout("Sair", "main", key="botao-sair", use_container_width=True)

    return menu


# ---------- Páginas ----------

def pagina_lancamento_manual():
    cabecalho("Lançamento Manual", "Registre um gasto de cartão ou um gasto avulso, como água e internet.")

    condicao = st.segmented_control("Condição", CONDICOES, default="Cartão", required=True)
    avulso = condicao == "Avulso"

    with st.form("lancamento", clear_on_submit=True, border=True):
        c1, c2, c3 = st.columns(3)
        data = c1.date_input("Data", format="DD/MM/YYYY")
        if avulso:
            banco = None
            motivo = c2.text_input("Motivo", placeholder="Ex.: Água, Internet, Luz")
        else:
            banco = c2.selectbox("Banco", BANCOS)
            motivo = None
        responsavel = c3.selectbox("Responsável", RESPONSAVEIS)

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
        inserir_gastos(df)
        st.toast("Lançamento salvo com sucesso!", icon="✅")


def pagina_importar_fatura():
    cabecalho("Importar Fatura", "Envie o PDF da fatura do cartão para importar as compras automaticamente.")

    c1, c2 = st.columns(2)
    banco = c1.selectbox("Banco do cartão", BANCOS)
    responsavel = c2.selectbox("Responsável pelas compras", RESPONSAVEIS)
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
        inserir_gastos(df)
        st.session_state.setdefault("faturas_importadas", set()).add(arquivo.file_id)
        avisar(f"{len(df)} compras importadas com sucesso!")


def pagina_historico():
    cabecalho("Histórico de Lançamentos", "Edite os lançamentos diretamente na tabela e clique em salvar.")

    df = carregar_gastos()
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
            "banco": st.column_config.SelectboxColumn("Banco", options=BANCOS),
            "responsavel": st.column_config.SelectboxColumn("Responsável", options=RESPONSAVEIS),
            "valor": st.column_config.NumberColumn("Valor", format="R$ %.2f", min_value=0.0),
            "parcela": st.column_config.TextColumn("Parcela"),
            "motivo": st.column_config.TextColumn("Motivo"),
        },
    )

    if st.button("Salvar alterações", icon=":material/save:", type="primary"):
        try:
            aplicar_alteracoes_editor(df, st.session_state[chave])
        except ValueError as erro:
            st.error(str(erro))
            return

        st.session_state["versao_historico"] = st.session_state.get("versao_historico", 0) + 1
        avisar("Alterações salvas!")


def pagina_por_mes():
    cabecalho("Análise por Mês", "Total de gastos em cada mês, dividido por responsável.")

    tabela = carregar_gastos()
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

    tabela = carregar_gastos()
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


PAGINAS = {
    "Lançamento Manual": pagina_lancamento_manual,
    "Importar fatura": pagina_importar_fatura,
    "Histórico": pagina_historico,
    "Por mês": pagina_por_mes,
    "Por banco": pagina_por_banco,
}


# ---------- Execução do app ----------

authenticator = autenticar()
menu = montar_sidebar(authenticator)
mostrar_aviso_pendente()

if menu in PAGINAS:
    PAGINAS[menu]()
