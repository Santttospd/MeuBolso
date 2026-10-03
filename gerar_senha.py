# Gera o hash de uma senha para colocar nos Secrets (campo "password").
# Uso: python gerar_senha.py
from getpass import getpass

import streamlit_authenticator as stauth

senha = getpass("Senha do novo usuário: ")
if senha != getpass("Repita a senha: "):
    raise SystemExit("As senhas não conferem.")

print("\nCole este valor no campo password do usuário nos Secrets:\n")
print(stauth.Hasher.hash(senha))
