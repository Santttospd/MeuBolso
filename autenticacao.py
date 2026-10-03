import streamlit_authenticator as stauth
import streamlit as st
from tema import cores

ESTILO_LOGIN = """
<style>
.login-topo {{ text-align: center; margin: 3rem 0 1.5rem; }}
.login-topo .login-icone {{ font-size: 3.5rem; line-height: 1; }}
.login-topo h1 {{ padding: 0.5rem 0 0; }}
.login-topo h1 span[data-testid="stHeaderActionElements"] {{ display: none; }}
.login-topo p {{ color: {texto_suave}; margin: 0; }}

[data-testid="stForm"] {{
    background-color: {secondaryBackgroundColor};
    border: 1px solid {borda};
    border-radius: 16px;
    padding: 1.5rem 1.75rem;
    box-shadow: 0 10px 30px {sombra};
}}
[data-testid="stForm"] h3 {{ text-align: center; padding-top: 0; }}
[data-testid="stForm"] [data-testid="stTextInputRootElement"],
[data-testid="stForm"] input {{ background-color: {backgroundColor}; }}

[data-testid="stElementContainer"]:has([data-testid="stFormSubmitButton"]),
[data-testid="stElementContainer"]:has([data-testid="stFormSubmitButton"]) > div,
[data-testid="stFormSubmitButton"] {{ width: 100%; }}
[data-testid="stFormSubmitButton"] button {{
    width: 100%;
    background-color: {primaryColor};
    border-color: {primaryColor};
    color: #FFFFFF;
    font-weight: 600;
}}
[data-testid="stFormSubmitButton"] button:hover {{
    filter: brightness(0.9);
    border-color: {primaryColor};
    color: #FFFFFF;
}}

</style>
"""

def autenticar():
    # Usuários e chave do cookie ficam nos Secrets (.streamlit/secrets.toml
    # localmente, ou em "Settings > Secrets" na Streamlit Cloud).
    try:
        configurado = "credentials" in st.secrets and "cookie" in st.secrets
    except Exception:  # sem arquivo de Secrets
        configurado = False
    if not configurado:
        st.error("Configuração de login ausente: defina [credentials] e [cookie] nos Secrets do app.")
        st.stop()

    cookie = st.secrets["cookie"]
    authenticator = stauth.Authenticate(
        st.secrets["credentials"].to_dict(),
        cookie["name"],
        cookie["key"],
        cookie["expiry_days"],
        auto_hash=False,
    )

    tela_login = st.empty()
    with tela_login.container():
        _, centro, _ = st.columns([1, 1.2, 1])
    with centro:
        st.markdown(ESTILO_LOGIN.format(**cores()), unsafe_allow_html=True)
        st.markdown(
            "<div class='login-topo'>"
            "<div class='login-icone'>💰</div>"
            "<h1>Meu Bolso</h1>"
            "<p>Controle de gastos da família</p>"
            "</div>",
            unsafe_allow_html=True,
        )

        authenticator.login(fields={
            "Form name": "Acesse sua conta",
            "Username": "Usuário",
            "Password": "Senha",
            "Login": "Entrar",
        })

        status = st.session_state.get("authentication_status")

        if not status:
            if status is False:
                st.error("Usuário ou senha incorretos")

            st.stop()

    tela_login.empty()
    return authenticator