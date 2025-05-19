# app.py

import re
import io
import pandas as pd
import pdfplumber
import streamlit as st

# ─── Configuração da página ────────────────────────────────────────────────────
st.set_page_config(page_title="DIRF Parser Avançado", layout="wide")
st.title("💼 Parser de Fontes Pagadoras — Breakdown por Código")

# ─── Uploader ───────────────────────────────────────────────────────────────────
uploaded_file = st.file_uploader(
    "📄 Faça upload do PDF das Fontes Pagadoras (DIRF)", 
    type=["pdf"]
)
if not uploaded_file:
    st.info("Aguardando upload do PDF...")
    st.stop()

st.info("🔍 Extraindo e estruturando os dados…")

# ─── Extrai todo o texto de cada página ─────────────────────────────────────────
lines = []
with pdfplumber.open(uploaded_file) as pdf:
    for page in pdf.pages:
        text = page.extract_text() or ""
        # preserva quebras de linha para identificar headers “quebrados”
        lines.extend(text.splitlines())

# ─── Definição de padrões de regex ──────────────────────────────────────────────
header_re = re.compile(
    r'^\s*(?P<cnpj>\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})\s+'       # CNPJ/CPF
    r'(?P<name>.+?)\s+'                                       # Nome (lazy)
    r'(?P<date>\d{2}/\d{2}/\d{4})\s+'                         # Data
    r'(?P<total_rend>[\d\.,]+)\s+'                            # Rendimento total
    r'(?P<total_ret>[\d\.,]+)\s*$'                            # Tributo total
)
code_re = re.compile(
    r'^\s*(?P<code>\d+)\s+'                                   # Código
    r'(?P<rend>[\d\.,]+)\s+'                                  # Rendimento
    r'(?P<ret>[\d\.,]+)\s*$'                                  # Tributo Retido
)

# ─── Parsing iterativo com contexto ───────────────────────────────────────────
records = []
current = {"cnpj": None, "name": None, "date": None}

i = 0
while i < len(lines):
    line = lines[i].strip()

    # 1) Tenta casar um header completo
    m = header_re.match(line)
    if not m and i + 1 < len(lines):
        # às vezes o nome quebra em duas linhas → concatena duas
        combo = line + " " + lines[i + 1].strip()
        m = header_re.match(combo)
        if m:
            i += 1  # consumiu a próxima linha no combo

    if m:
        # atualiza contexto
        current["cnpj"] = m.group("cnpj")
        current["name"] = m.group("name")
        current["date"] = m.group("date")
        i += 1
        continue

    # 2) Se for linha de código e tivermos contexto válido, registra
    cm = code_re.match(line)
    if cm and current["cnpj"]:
        records.append({
            "CNPJ / CPF": current["cnpj"],
            "Nome Empresarial/Nome": current["name"],
            "Data do Processamento": current["date"],
            "Código": cm.group("code"),
            "Rendimento Tributável": cm.group("rend").replace(".", "").replace(",", "."),
            "Tributo Retido": cm.group("ret").replace(".", "").replace(",", "."),
        })

    i += 1

# ─── Validação do parsing ──────────────────────────────────────────────────────
if not records:
    st.error("❌ Não encontrei nenhuma fonte pagadora. Verifique o layout do PDF.")
    st.stop()

# ─── Construção do DataFrame e conversões ───────────────────────────────────────
df = pd.DataFrame.from_records(records)
df["Data do Processamento"] = pd.to_datetime(df["Data do Processamento"], dayfirst=True, errors="coerce")
df["Rendimento Tributável"] = df["Rendimento Tributável"].astype(float)
df["Tributo Retido"]       = df["Tributo Retido"].astype(float)

st.success(f"✅ Extraídas {len(df):,} linhas no total.")
st.dataframe(df)

# ─── Exportação para Excel ─────────────────────────────────────────────────────
output = io.BytesIO()
with pd.ExcelWriter(output, engine="openpyxl") as writer:
    df.to_excel(writer, index=False, sheet_name="FontesPagadoras")
output.seek(0)

st.download_button(
    label="⬇️ Baixar relatorio completo (Excel)",
    data=output,
    file_name="fontes_pagadoras_breakdown.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)
