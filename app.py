# -*- coding: utf-8 -*-
"""Aplicação Streamlit com múltiplas páginas para processamento de XML:
1. Extrair Tags (com filtro opcional)
2. Consolidar Faturas por UF
"""

import streamlit as st
import pandas as pd
from xml_parser import process_files, consolidate_faturas_by_uf # Importa ambas as funções
import io
import datetime

st.set_page_config(layout="wide", page_title="Processador XML Fiscal")

# --- Definição das Páginas --- 
def page_extract_tags():
    st.title("🔎 Ferramenta de Extração de Dados XML (com Filtro Opcional)")
    st.markdown("""
    Carregue arquivos XML, extraia valores de uma tag específica e, opcionalmente,
    filtre os resultados com base no valor de outra tag dentro de um mesmo elemento ancestral comum.
    """)

    # --- Upload de Arquivos ---
    st.header("1. Carregue seus arquivos XML")
    uploaded_files = st.file_uploader(
        "Selecione um ou mais arquivos XML para extração",
        type=["xml"],
        accept_multiple_files=True,
        key="uploader_extracao", # Chave única para este uploader
        help="Você pode selecionar múltiplos arquivos. O limite de upload está ajustado para arquivos grandes."
    )

    # --- Input da Tag Alvo ---
    st.header("2. Informe a Tag Alvo")
    tag_name = st.text_input(
        "Nome da Tag Alvo",
        placeholder="Ex: nNF, dhEmi, CNPJ",
        key="tag_alvo_extracao",
        help="Digite o nome exato da tag XML cujo valor você deseja extrair (sem < >)."
    )

    # --- Filtro Opcional ---
    st.header("3. Filtro (Opcional)")
    st.markdown("Preencha os campos abaixo *apenas* se desejar extrair a Tag Alvo condicionalmente.")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        parent_tag = st.text_input(
            "Tag Ancestral Comum (Contexto)",
            placeholder="Ex: infNFCom, ide, emit",
            key="parent_tag_extracao",
            help="Tag ancestral comum que contém *tanto* a tag de filtro quanto a tag alvo (mesmo que em níveis diferentes). Ex: infNFCom, registro. Deixe em branco se não for filtrar."
        )
    with col2:
        filter_tag = st.text_input(
            "Tag de Filtro",
            placeholder="Ex: cUF, UF, tpAmb",
            key="filter_tag_extracao",
            help="Tag usada como condição para o filtro. Deixe em branco se não for filtrar."
        )
    with col3:
        filter_value = st.text_input(
            "Valor do Filtro",
            placeholder="Ex: 31, SP, 1",
            key="filter_value_extracao",
            help="Valor que a Tag de Filtro deve ter. Deixe em branco se não for filtrar."
        )

    # --- Botão de Processamento e Resultados ---
    st.header("4. Processe e veja os resultados")
    if st.button("Extrair Dados", type="primary", key="btn_extracao"):
        if not uploaded_files:
            st.error("Por favor, carregue pelo menos um arquivo XML.")
        elif not tag_name:
            st.error("Por favor, informe o nome da Tag Alvo.")
        else:
            is_filtering = bool(parent_tag and filter_tag and filter_value)
            filter_info_for_spinner = f" com filtro `{filter_tag}`=`{filter_value}` no contexto `{parent_tag}`" if is_filtering else ""

            with st.spinner(f"Processando arquivos e buscando pela tag `{tag_name}`{filter_info_for_spinner}... Isso pode levar alguns minutos."):
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
                df_results = df_results[["Nome do Arquivo", "TAG", "Filtro", "Valor", "Ocorrência"]]
                st.dataframe(df_results, use_container_width=True)

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
                    key="download_csv_extracao"
                )
            else:
                st.warning("Nenhum resultado encontrado ou ocorreu um erro. Verifique os arquivos, a tag e os critérios de filtro.")

def page_consolidate_faturas():
    st.title("📄 Ferramenta de Consolidação de Faturas por UF")
    st.markdown("""
    Carregue um ou mais arquivos XML contendo blocos `<Fatura>`. A ferramenta irá encontrar
    todas as Faturas onde a tag `<UF>` (dentro de `<enderEmit>`) corresponda ao valor informado
    e criará um novo arquivo XML `<loteNFCom>` contendo apenas essas faturas.
    """)

    # --- Upload de Arquivos ---
    st.header("1. Carregue os arquivos XML de origem")
    uploaded_files_consolidacao = st.file_uploader(
        "Selecione um ou mais arquivos XML para consolidação",
        type=["xml"],
        accept_multiple_files=True,
        key="uploader_consolidacao", # Chave única
        help="Você pode selecionar múltiplos arquivos que contenham as Faturas."
    )

    # --- Inputs para Consolidação ---
    st.header("2. Informe os parâmetros para consolidação")
    col1_cons, col2_cons = st.columns(2)
    with col1_cons:
        target_uf = st.text_input(
            "UF para Filtrar",
            placeholder="Ex: SP, MG, RJ",
            key="uf_consolidacao",
            help="Digite a sigla da UF (ex: SP) para incluir apenas as Faturas dessa UF."
        )
    with col2_cons:
        numero_lote = st.text_input(
            "Número do Lote",
            placeholder="Ex: 0000000430",
            key="lote_consolidacao",
            help="Digite o número que será usado no atributo NUMERO_LOTE do arquivo consolidado."
        )

    # --- Botão de Processamento e Download ---
    st.header("3. Gere o arquivo consolidado")
    if st.button("Consolidar Faturas", type="primary", key="btn_consolidacao"):
        if not uploaded_files_consolidacao:
            st.error("Por favor, carregue pelo menos um arquivo XML de origem.")
        elif not target_uf:
            st.error("Por favor, informe a UF para filtrar as faturas.")
        elif not numero_lote:
            st.error("Por favor, informe o Número do Lote para o arquivo consolidado.")
        else:
            with st.spinner(f"Processando arquivos e consolidando Faturas da UF '{target_uf}'... Isso pode levar alguns minutos."):
                consolidated_xml_str, fatura_count = consolidate_faturas_by_uf(
                    files=uploaded_files_consolidacao,
                    target_uf=target_uf.upper(), # Garante que a UF seja maiúscula para comparação
                    numero_lote=numero_lote
                )
            
            if consolidated_xml_str and fatura_count > 0:
                st.success(f"Consolidação concluída! {fatura_count} fatura(s) da UF '{target_uf}' foram encontradas e agrupadas.")
                
                st.subheader("Download do Arquivo Consolidado")
                st.download_button(
                    label=f"Baixar lote_{numero_lote}_{target_uf}.xml",
                    data=consolidated_xml_str,
                    file_name=f"lote_{numero_lote}_{target_uf}.xml",
                    mime="application/xml",
                    key="download_xml_consolidado"
                )
                
                # Opcional: Mostrar prévia do XML gerado (pode ser lento/grande)
                # with st.expander("Prévia do XML Consolidado (início)"):
                #     st.code(consolidated_xml_str[:2000] + "...", language="xml")
                    
            elif fatura_count == 0:
                st.warning(f"Nenhuma fatura encontrada para a UF '{target_uf}' nos arquivos fornecidos.")
            else: # Erro
                st.error("Ocorreu um erro durante a consolidação. Verifique os logs ou os arquivos de entrada.")

# --- Navegação Principal (Sidebar) ---
st.sidebar.title("Menu de Ferramentas")
page = st.sidebar.radio("Escolha a ferramenta:", ("Extrair Tags", "Consolidar Faturas por UF"))

st.sidebar.markdown("--- ")
st.sidebar.caption("Desenvolvido com Python e Streamlit.")

# --- Executa a página selecionada ---
if page == "Extrair Tags":
    page_extract_tags()
elif page == "Consolidar Faturas por UF":
    page_consolidate_faturas()

