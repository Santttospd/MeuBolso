import streamlit_authenticator as stauth
import streamlit as st
from sqlalchemy.exc import IntegrityError

from banco import carregar_usuarios, criar_usuario, importar_usuarios

# Cores derivadas da cor do texto (currentColor): funcionam no tema claro e no escuro
ESTILO_LOGIN = """
<style>
.login-topo { text-align: center; margin: 3rem 0 1.5rem; }
.login-topo .login-icone { font-size: 3.5rem; line-height: 1; }
.login-topo h1 { padding: 0.5rem 0 0; }
.login-topo h1 span[data-testid="stHeaderActionElements"] { display: none; }
.login-topo p { opacity: 0.65; margin: 0; }

[data-testid="stForm"] {
    background-color: color-mix(in srgb, currentColor 5%, transparent);
    border: 1px solid color-mix(in srgb, currentColor 15%, transparent);
    border-radius: 16px;
    padding: 1.5rem 1.75rem;
    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.15);
}
[data-testid="stForm"] h3 { text-align: center; padding-top: 0; }
[data-testid="stTabs"] [role="tablist"] [data-testid="stTab"] { flex: 1; justify-content: center; }
[data-testid="stTabs"] [data-testid="stImage"] img { border-radius: 8px; }

[data-testid="stElementContainer"]:has([data-testid="stFormSubmitButton"]),
[data-testid="stElementContainer"]:has([data-testid="stFormSubmitButton"]) > div,
[data-testid="stFormSubmitButton"] { width: 100%; }
[data-testid="stFormSubmitButton"] button {
    width: 100%;
    background-color: #16A34A;
    border-color: #16A34A;
    color: #FFFFFF;
    font-weight: 600;
}
[data-testid="stFormSubmitButton"] button:hover {
    filter: brightness(0.92);
    border-color: #16A34A;
    color: #FFFFFF;
}
</style>
"""

MENSAGENS_CADASTRO = {
    "Email already taken": "Este e-mail já está cadastrado.",
    "Username/email already taken": "Este nome de usuário já está em uso.",
    "Email is not valid": "E-mail inválido.",
    "Username is not valid": "Nome de usuário inválido. Use letras, números, ponto, hífen ou sublinhado.",
    "First name is not valid": "Nome inválido.",
    "Last name is not valid": "Sobrenome inválido.",
    "Passwords do not match": "As senhas não conferem.",
    "Password/repeat password fields cannot be empty": "Preencha a senha nos dois campos.",
    "Captcha not entered": "Digite o código da imagem.",
    "Captcha entered incorrectly": "Código da imagem incorreto. Tente de novo.",
}
REGRAS_SENHA = "A senha precisa ter de 8 a 20 caracteres, com letra maiúscula, minúscula, número e símbolo (ex.: @ ! #)."


def _traduzir_erro(erro):
    texto = str(erro)
    if texto.startswith("**Password must:**"):
        return REGRAS_SENHA
    return MENSAGENS_CADASTRO.get(texto, texto)


@st.cache_resource
def _importar_usuarios_dos_secrets():
    # Usuários antigos, definidos nos Secrets, passam a morar no banco
    if "credentials" in st.secrets:
        importar_usuarios(st.secrets["credentials"].to_dict())


def _formulario_cadastro(authenticator, credenciais):
    st.caption(REGRAS_SENHA)
    try:
        email, usuario, nome = authenticator.register_user(
            fields={
                "Form name": "Crie sua conta",
                "First name": "Nome",
                "Last name": "Sobrenome",
                "Email": "E-mail",
                "Username": "Usuário",
                "Password": "Senha",
                "Repeat password": "Repita a senha",
                "Captcha": "Código da imagem",
                "Register": "Criar conta",
            },
            captcha=True,
            password_hint=False,
        )
    except Exception as erro:
        st.error(_traduzir_erro(erro))
        return

    if email:
        try:
            criar_usuario(usuario, credenciais["usernames"][usuario])
        except IntegrityError:
            st.error("Este usuário ou e-mail já está cadastrado.")
            return
        st.success(f"Conta criada, {nome.split()[0]}! Agora é só entrar na aba **Entrar**.")


def autenticar():
    # A chave do cookie fica nos Secrets (.streamlit/secrets.toml localmente,
    # ou em "Settings > Secrets" na Streamlit Cloud). Os usuários ficam no banco.
    try:
        configurado = "cookie" in st.secrets
    except Exception:  # sem arquivo de Secrets
        configurado = False
    if not configurado:
        st.error("Configuração de login ausente: defina [cookie] nos Secrets do app.")
        st.stop()

    _importar_usuarios_dos_secrets()
    credenciais = carregar_usuarios()

    cookie = st.secrets["cookie"]
    authenticator = stauth.Authenticate(
        credenciais,
        cookie["name"],
        cookie["key"],
        cookie["expiry_days"],
        auto_hash=False,
    )

    tela_login = st.empty()
    with tela_login.container():
        _, centro, _ = st.columns([1, 1.2, 1])
    with centro:
        st.markdown(ESTILO_LOGIN, unsafe_allow_html=True)
        st.markdown(
            "<div class='login-topo'>"
            "<div class='login-icone'>💰</div>"
            "<h1>Meu Bolso</h1>"
            "<p>Controle seus gastos de um jeito simples</p>"
            "</div>",
            unsafe_allow_html=True,
        )

        aba_entrar, aba_cadastro = st.tabs(["Entrar", "Criar conta"])
        with aba_entrar:
            authenticator.login(fields={
                "Form name": "Acesse sua conta",
                "Username": "Usuário",
                "Password": "Senha",
                "Login": "Entrar",
            })
            status = st.session_state.get("authentication_status")
            if status is False:
                st.error("Usuário ou senha incorretos")

        if not status:
            with aba_cadastro:
                _formulario_cadastro(authenticator, credenciais)
            st.stop()

    tela_login.empty()
    return authenticator
