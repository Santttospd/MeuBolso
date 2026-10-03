import streamlit as st
from banco import ler_preferencia, salvar_preferencia

TEMAS = {
    "dark": {
        "primaryColor": "#22C55E",
        "backgroundColor": "#0F172A",
        "secondaryBackgroundColor": "#1E293B",
        "textColor": "#E2E8F0",
        "borda": "#334155",
        "texto_suave": "#94A3B8",
        "sombra": "rgba(0, 0, 0, 0.35)",
        "plotly": "plotly_dark",
    },
    "light": {
        "primaryColor": "#16A34A",
        "backgroundColor": "#F8FAFC",
        "secondaryBackgroundColor": "#E2E8F0",
        "textColor": "#0F172A",
        "borda": "#CBD5E1",
        "texto_suave": "#64748B",
        "sombra": "rgba(15, 23, 42, 0.08)",
        "plotly": "plotly_white",
    },
}

OPCOES_STREAMLIT = ["primaryColor", "backgroundColor", "secondaryBackgroundColor", "textColor"]


def tema_atual():
    return "light" if st.get_option("theme.base") == "light" else "dark"


def cores():
    return TEMAS[tema_atual()]


def _definir_opcoes(nome):
    # O Streamlit não tem API pública para isso: alteramos a configuração do
    # servidor, que é reenviada ao navegador na próxima execução do script.
    st._config.set_option("theme.base", nome)
    for opcao in OPCOES_STREAMLIT:
        st._config.set_option(f"theme.{opcao}", TEMAS[nome][opcao])


@st.cache_resource
def tema_salvo():
    # Lido do banco uma vez por processo; trocar_tema limpa este cache.
    nome = ler_preferencia("tema")
    return nome if nome in TEMAS else None


def aplicar_tema_salvo():
    # Ao reiniciar o servidor, o config.toml volta a valer; reaplicamos o tema salvo.
    nome = tema_salvo()
    if nome and nome != tema_atual():
        _definir_opcoes(nome)
        st.rerun()


def trocar_tema(nome):
    salvar_preferencia("tema", nome)
    tema_salvo.clear()
    _definir_opcoes(nome)
    st.rerun()
