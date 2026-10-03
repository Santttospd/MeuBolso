import pdfplumber
import re
import pandas as pd


class FaturaInvalida(Exception):
    pass


def converter_valor(texto):
    texto = texto.replace(".", "")
    texto = texto.replace(",", ".")
    return float(texto)


def ler_fatura(arquivo, banco="Mercado Pago", responsavel="Pedro"):
    # Lê o layout da fatura do Mercado Pago: compras na 2ª página.
    try:
        with pdfplumber.open(arquivo) as pdf:
            if len(pdf.pages) < 2:
                raise FaturaInvalida("O PDF tem só uma página; a fatura esperada tem as compras na 2ª página.")
            texto = pdf.pages[1].extract_text() or ""
    except FaturaInvalida:
        raise
    except Exception as erro:
        raise FaturaInvalida("Não foi possível abrir o arquivo. Confira se é um PDF válido.") from erro

    vencimento = re.search(r"Vencimento: (\d{2})/(\d{2})/(\d{4})", texto)
    if not vencimento:
        raise FaturaInvalida("Não encontrei a data de vencimento. Este arquivo parece não ser uma fatura do Mercado Pago.")
    dia, mes, ano = vencimento.groups()
    data_fatura = f"{ano}-{mes}-{dia}"

    compras = []
    cartao_atual = None

    for linha in texto.split("\n"):
        if linha.startswith("Cartão"):
            cartao_atual = linha[-5:-1]
        if re.match(r"^\d{2}/\d{2}", linha) and cartao_atual and "R$ " in linha:
            try:
                valor = converter_valor(linha.split("R$ ")[-1])
            except ValueError:
                continue

            parcela = re.search(r"Parcela (\d+) de (\d+)", linha)
            if parcela:
                parcela_texto = f"{parcela.group(1)}/{parcela.group(2)}"
            else:
                parcela_texto = "1/1"

            compras.append({
                "data": data_fatura,
                "condicao": "Cartão",
                "banco": banco,
                "responsavel": responsavel,
                "valor": valor,
                "parcela": parcela_texto,
            })

    if not compras:
        raise FaturaInvalida("Nenhuma compra encontrada na fatura.")

    return pd.DataFrame(compras)
