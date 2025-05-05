import streamlit as st
import pandas as pd
from xml_parser import process_files # Importa a função atualizada
import io

st.set_page_config(layout="wide", page_title="Extrator de Dados XML com Filtro")

st.title("🔎 Ferramenta de Extração de Dados XML (com Filtro Opcional)")
st.markdown("""
Esta ferramenta permite carregar arquivos XML, extrair valores de uma tag específica e, opcionalmente,
filtrar os resultados com base no valor de outra tag dentro de um mesmo elemento pai.
""")

# --- Upload de Arquivos ---
st.header("1. Carregue seus arquivos XML")
uploaded_files = st.file_uploader(
    "Selecione um ou mais arquivos XML",
    type=["xml"],
    accept_multiple_files=True,
    help="Você pode selecionar múltiplos arquivos. O limite de upload está ajustado para arquivos grandes."
)

# --- Input da Tag Alvo ---
st.header("2. Informe a Tag Alvo")
tag_name = st.text_input(
    "Nome da Tag Alvo",
    placeholder="Ex: nNF, dhEmi, CNPJ",
    help="Digite o nome exato da tag XML cujo valor você deseja extrair (sem < >)."
)

# --- Filtro Opcional ---
st.header("3. Filtro (Opcional)")
st.markdown("Preencha os campos abaixo *apenas* se desejar extrair a Tag Alvo condicionalmente.")

col1, col2, col3 = st.columns(3)

with col1:
    parent_tag = st.text_input(
        "Tag Pai (Contexto)",
        placeholder="Ex: ide, emit",
        help="Tag ancestral comum que contém *tanto* a tag de filtro quanto a tag alvo (mesmo que em níveis diferentes). Ex: infNFCom, registro. Deixe em branco se não for filtrar."
    )
with col2:
    filter_tag = st.text_input(
        "Tag de Filtro",
        placeholder="Ex: cUF, tpAmb",
        help="Tag usada como condição para o filtro. Deixe em branco se não for filtrar."
    )
with col3:
    filter_value = st.text_input(
        "Valor do Filtro",
        placeholder="Ex: 31, 1",
        help="Valor que a Tag de Filtro deve ter. Deixe em branco se não for filtrar."
    )

# --- Botão de Processamento e Resultados ---
st.header("4. Processe e veja os resultados")

if st.button("Extrair Dados", type="primary"):
    # Validar inputs básicos
    if not uploaded_files:
        st.error("Por favor, carregue pelo menos um arquivo XML.")
    elif not tag_name:
        st.error("Por favor, informe o nome da Tag Alvo.")
    else:
        # Verificar se o filtro está sendo usado (todos os campos de filtro preenchidos)
        is_filtering = bool(parent_tag and filter_tag and filter_value)
        filter_info_for_spinner = f" com filtro `{filter_tag}`=`{filter_value}` no contexto `{parent_tag}`" if is_filtering else ""

        with st.spinner(f"Processando arquivos e buscando pela tag `{tag_name}`{filter_info_for_spinner}... Isso pode levar alguns minutos para arquivos grandes."):
            # Chama a função de processamento, passando os parâmetros de filtro se existirem
            results_list = process_files(
                files=uploaded_files,
                tag_name=tag_name,
                parent_tag=parent_tag if is_filtering else None,
                filter_tag=filter_tag if is_filtering else None,
                filter_value=filter_value if is_filtering else None
            )

        if results_list:
            st.success("Processamento concluído!")
            df_results = pd.DataFrame(results_list)

            # Reordenar colunas, incluindo a coluna Filtro
            df_results = df_results[["Nome do Arquivo", "TAG", "Filtro", "Valor", "Ocorrência"]]

            st.dataframe(df_results, use_container_width=True)

            # --- Download dos Resultados ---
            st.subheader("Download dos Resultados")

            @st.cache_data
            def convert_df_to_csv(df):
                output = io.StringIO()
                df.to_csv(output, index=False, encoding="utf-8")
                return output.getvalue()

            csv_data = convert_df_to_csv(df_results)
            csv_filename = f"extracao_{tag_name}_filtrado.csv" if is_filtering else f"extracao_{tag_name}.csv"

            st.download_button(
                label="Baixar resultados como CSV",
                data=csv_data,
                file_name=csv_filename,
                mime="text/csv",
            )
        else:
            st.warning("Nenhum resultado encontrado ou ocorreu um erro durante o processamento. Verifique os arquivos, a tag e os critérios de filtro informados.")

st.markdown("--- ")
st.caption("Desenvolvido com Python e Streamlit.")

