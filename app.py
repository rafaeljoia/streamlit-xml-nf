# -*- coding: utf-8 -*-
import io
import datetime
import streamlit as st
from streamlit_option_menu import option_menu
import pandas as pd
from xml_parser import (
    consolidate_faturas_by_result,
    format_uf,
    process_files,
)


st.set_page_config(
    layout="wide", page_title="Buscador XML Fiscal", page_icon="🔍", menu_items={}
)

for key in [
    "parent_tag_extracao",
    "filter_parent_path_extracao",
    "filter_tag_extracao",
    "filter_value_extracao",
]:
    if key not in st.session_state:
        st.session_state[key] = ""


def limpar_campos():
    st.session_state["parent_tag_extracao"] = ""
    st.session_state["filter_parent_path_extracao"] = ""
    st.session_state["filter_tag_extracao"] = ""
    st.session_state["filter_value_extracao"] = ""


# --- Definição das Páginas ---
def page_extract_tags():
    st.title("🔎 Buscador de Dados XML")
    st.markdown(
        """
    Carregue arquivos XML e extraia valores de uma tag específica.
    """
    )

    st.header("1. Carregue seus arquivos XML")
    uploaded_files = st.file_uploader(
        "Selecione um ou mais arquivos XML para extração",
        type=["xml"],
        accept_multiple_files=True,
        key="uploader_extracao",
        help="Você pode selecionar múltiplos arquivos.",
    )

    st.header("2. Informe a Tag de Busca")
    tag_name = st.text_input(
        "Nome da Tag de Busca",
        placeholder="Ex: nNF, dhEmi, CNPJ",
        key="tag_alvo_extracao",
        help="Digite o nome exato da tag XML cujo valor você deseja extrair (sem < >).",
    )

    st.header("3. Filtro (Opcional)")
    st.markdown(
        "Preencha os campos abaixo *apenas* se desejar extrair a Tag de Busca condicionalmente. Caso contrário, a busca será ampla em todos os nós do XML."
    )

    col1, col2 = st.columns(2)
    with col1:
        parent_tag = st.text_input(
            "Tag Contexto (PAI)",
            placeholder="Ex: enderDest",
            key="parent_tag_extracao",
            help="Tag ancestral comum que contém *tanto* a tag de filtro quanto a tag alvo. Ex: infNFCom, NFe. Deixe em branco se não for filtrar.",
        )
    with col2:
        filter_parent_path_input = st.text_input(
            "Tag Contexto (FILHO) - opcional, relativo a tag contexto pai",
            placeholder="Ex: dest, ide/total",
            key="filter_parent_path_extracao",
            help="Caminho para o nó que contém a Tag de Filtro, relativo à Tag Contexto. Ex: se Ancestral é 'infNFCom' e quer filtrar por 'dest/xNome', digite 'dest' aqui e 'xNome' em 'Tag de Filtro'. Deixe em branco se a Tag de Filtro estiver diretamente sob o Ancestral ou para busca ampla.",
        )

    col_filter_tag, col_filter_value = st.columns(2)
    with col_filter_tag:
        filter_tag = st.text_input(
            "Tag de Filtro",
            placeholder="Ex: UF",
            key="filter_tag_extracao",
            help="Tag usada como condição para o filtro. Deixe em branco se não for filtrar.",
        )
    with col_filter_value:
        filter_value = st.text_input(
            "Valor do Filtro",
            placeholder="Ex: SP",
            key="filter_value_extracao",
            help="Valor que a Tag de Filtro deve ter. Deixe em branco se não for filtrar.",
        )

    st.button(
        "🔄 Limpar Filtros", on_click=limpar_campos, type="secondary", key="btn_limpar"
    )

    st.header("4. Processamento")
    if st.button("Extrair Dados", type="primary", key="btn_extracao"):
        if not uploaded_files:
            st.error("Por favor, carregue pelo menos um arquivo XML.")
        elif not tag_name:
            st.error("Por favor, informe o nome da Tag de Busca.")
        else:
            is_filtering = bool(parent_tag and filter_tag and filter_value)

            filter_info_parts = []
            if parent_tag:
                filter_info_parts.append(f"Contexto: `{parent_tag}`")
            if filter_tag:
                filter_info_parts.append(f"Tag Filtro: `{filter_tag}`")
            if filter_parent_path_input:
                filter_info_parts.append(
                    f"Caminho Filtro: `{filter_parent_path_input}`"
                )

            if filter_value:
                filter_info_parts.append(f"Valor Filtro: `{filter_value}`")
            filter_info_for_spinner = (
                f" com filtro ({', '.join(filter_info_parts)})" if is_filtering else ""
            )
            result_list = []
            with st.spinner(
                f"Processando arquivos e buscando pela tag `{tag_name}`{filter_info_for_spinner}... Isso pode levar alguns minutos."
            ):
                results_list = process_files(
                    files=uploaded_files,
                    tag_name=tag_name,
                    parent_tag=parent_tag if is_filtering else None,
                    filter_tag=filter_tag if is_filtering else None,
                    filter_value=filter_value if is_filtering else None,
                    filter_parent_path=(
                        filter_parent_path_input
                        if is_filtering and filter_parent_path_input
                        else None
                    ),  # Passa o novo campo
                )

            st.session_state["results_list"] = results_list
            st.session_state["uploaded_files"] = uploaded_files
            st.session_state["tag_name"] = tag_name

            if results_list:
                st.success("Processamento concluído!")
                df_results = pd.DataFrame(results_list)

                if tag_name == "cUF":
                    df_results["Valor"] = df_results["Valor"].apply(format_uf)

                cols_to_show = [
                    "Nome do Arquivo",
                    "TAG",
                    "Filtro",
                    "Valor",
                    "Ocorrência",
                ]

                df_results_display = pd.DataFrame(columns=cols_to_show)
                for col in cols_to_show:
                    if col in df_results.columns:
                        df_results_display[col] = df_results[col]
                    else:
                        df_results_display[col] = None

                df_results_display.index = df_results_display.index + 1
                st.dataframe(df_results_display, use_container_width=True)

                total_ocorrencia = df_results["Ocorrência"].sum()

                st.markdown(f"**TOTAL de Ocorrências: {total_ocorrencia}**")

                st.subheader("Download dos Resultados")

                @st.cache_data
                def convert_df_to_csv(df_to_convert):
                    output = io.StringIO()
                    df_to_convert.to_csv(output, index=False, encoding="utf-8-sig")
                    return output.getvalue()

                @st.cache_data
                def convert_df_to_excel(df):
                    output = io.BytesIO()
                    with pd.ExcelWriter(output, engine="openpyxl") as writer:
                        df.to_excel(writer, index=False, sheet_name="Sheet1")
                        data = output.getvalue()
                        return data

                csv_data = convert_df_to_csv(df_results_display)
                csv_filename = (
                    f"extracao_{tag_name}_filtrado.csv"
                    if is_filtering
                    else f"extracao_{tag_name}.csv"
                )
                st.download_button(
                    label="Baixar CSV",
                    data=csv_data,
                    file_name=csv_filename,
                    mime="text/csv",
                    key="download_csv_extracao",
                )

                excel_data = convert_df_to_excel(df_results)
                excel_filename = (
                    f"extracao_{tag_name}_filtrado.xlsx"
                    if is_filtering
                    else f"extracao_{tag_name}.xlsx"
                )
                st.download_button(
                    label="Baixar Excel",
                    data=excel_data,
                    file_name=excel_filename,
                    key="download_excel_extracao",
                    mime="application/vnd.ms-excel",
                )
                st.session_state["mostrar_botao_consolidar"] = True

            else:
                st.warning(
                    "Nenhum resultado encontrado ou ocorreu um erro. Verifique os arquivos, tag e filtros."
                )

    if (
        st.session_state.get("mostrar_botao_consolidar")
        and st.session_state.get("results_list")
        and st.session_state.get("tag_name") == "nNF"
    ):
        consolidar = st.button(
            "Consolidar Faturas", type="primary", key="btn_consolidacao"
        )
        if consolidar:
            numero_lote = datetime.datetime.now().strftime("%d%m%Y_%H%M%S")
            with st.spinner("Consolidando em XML..."):
                consolidated_xml_str, fatura_count = consolidate_faturas_by_result(
                    files=st.session_state["uploaded_files"],
                    results=st.session_state["results_list"],
                    numero_lote=numero_lote,
                )

            if consolidated_xml_str and fatura_count > 0:
                st.success(f"{fatura_count} fatura(s) consolidadas com sucesso.")
                st.download_button(
                    label=f"Baixar lote_{numero_lote}.xml",
                    data=consolidated_xml_str.encode("utf-8"),
                    file_name=f"lote_{numero_lote}.xml",
                    mime="application/xml",
                    key="download_xml_consolidado",
                )
            else:
                st.warning("Nenhuma fatura encontrada para consolidação.")


def page_guide():
    st.title("Guia de Uso")
    st.markdown("#### - Processo de Filtragem Comum")
    st.markdown(
        "Utilize o filtro `cUF` para obter a quantidade de UFs presentes nos arquivos XML."
    )
    st.markdown("Exemplo:")

    st.image(
        "img/filtro_cUF.jpg",
        caption="**Filtro cUF** – representa o código da UF extraído dos XMLs",
    )

    st.markdown("---")
    st.markdown(
        "Utilize o filtro `codigo_filial` para obter a quantidade de Filiais presentes nos arquivos XML."
    )
    st.markdown("Exemplo:")

    st.image(
        "img/filtro_codigo_filial.jpg",
        caption="**Filtro codigo_filial** – representa o codigo_filial extraído dos XMLs",
    )

    st.markdown("#### - Processo de Filtragem Avançada")

    st.markdown(
        "Utilize o filtro `nNF` para obter as NFs de determinado estado (UF),"
        "para isso, informe os filtros opcionais conforme figura abaixo."
    )

    st.markdown("Exemplo:")

    st.image(
        "img/filtro_nNF_UF.jpg",
        caption="**Filtro nNF** – representa notas filtradas por UF extraídas dos XMLs",
    )

    st.markdown("#### - Geração de Consolidado XML")
    st.markdown(
        "O botão de Consolidar Faturas, só estará disponível quando"
        "a opção do filtro for pela Nota Fiscal - tag nNF`."
        "Ao clicar no botão, será gerado um arquivo XML com as notas fiscais indicadas na tabela de resultados."
    )

    st.markdown("Exemplo:")

    st.image(
        "img/extracao_consolidado.jpg",
        caption="**Filtro nNF** – Export de XML das NFs",
    )


with st.sidebar:
    selected = option_menu(
        "Menu",
        options=["Buscar Tags", "Guia de Uso"],
        icons=["search", "book"],
        menu_icon="cast",
        default_index=0,
    )

st.sidebar.markdown("--- ")

if selected == "Buscar Tags":
    page_extract_tags()
elif selected == "Guia de Uso":
    page_guide()
