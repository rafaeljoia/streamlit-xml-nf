# -*- coding: utf-8 -*-
import os
from lxml import etree
from collections import Counter
import io
import datetime


def extract_tag_data(xml_source, tag_name):
    tag_values_counter = Counter()
    try:
        context = etree.iterparse(
            xml_source, events=("end",), tag=tag_name, recover=True
        )
        for event, elem in context:
            text_content = elem.text.strip() if elem.text else ""
            tag_values_counter[text_content] += 1
            elem.clear()

            while elem.getprevious() is not None:
                del elem.getparent()[0]
        return tag_values_counter
    except etree.XMLSyntaxError as e:
        print(f"Erro de sintaxe XML (extract_tag_data): {e}")
        return None
    except Exception as e:
        print(f"Erro inesperado (extract_tag_data): {e}")
        return None


def extract_filtered_tag_data(
    xml_source,
    common_ancestor_tag,
    filter_tag,
    filter_value,
    target_tag,
    filter_parent_path=None,
):

    target_values_counter = Counter()
    try:
        context = etree.iterparse(
            xml_source, events=("end",), tag="Fatura", recover=True
        )
        for event, ancestor_elem in context:
            filter_match = False
            target_value_found_in_context = None  # Renomeado para clareza

            xpath_filter_tag = filter_tag
            if filter_parent_path:
                clean_path = "/".join(
                    p for p in filter_parent_path.strip("/").split("/") if p
                )
                if clean_path:
                    xpath_filter_tag = f"{clean_path}/{filter_tag}"

            fatura_element = ancestor_elem.find(".//" + common_ancestor_tag)
            filter_elements = fatura_element.xpath(f"./{xpath_filter_tag}")

            if not filter_elements and not filter_parent_path:
                filter_elements = fatura_element.xpath(f".//{filter_tag}")

            for filter_elem_item in filter_elements:
                if (
                    filter_elem_item.text
                    and filter_elem_item.text.strip() == filter_value
                ):
                    filter_match = True
                    break

            # match de arquivo, para nNF uma nova regra
            if filter_match and target_tag == "nNF":

                target_elements = ancestor_elem.xpath(f".//{target_tag}")
                if target_elements and target_elements[0].text:
                    target_value_found_in_context = target_elements[0].text.strip()
                else:
                    target_value_found_in_context = (
                        "[TAG ALVO NÃO ENCONTRADA/VAZIA NO CONTEXTO DO FILTRO]"
                    )
                target_values_counter[target_value_found_in_context] += 1

            if filter_match and not target_tag == "nNF":

                target_elements = fatura_element.xpath(f".//{target_tag}")
                if target_elements and target_elements[0].text:
                    target_value_found_in_context = target_elements[0].text.strip()
                else:
                    target_value_found_in_context = (
                        "[TAG ALVO NÃO ENCONTRADA/VAZIA NO CONTEXTO DO FILTRO]"
                    )
                target_values_counter[target_value_found_in_context] += 1

            fatura_element.clear()
            while fatura_element.getprevious() is not None:
                del fatura_element.getparent()[0]
        return target_values_counter
    except etree.XMLSyntaxError as e:
        print(f"Erro de sintaxe XML (extract_filtered_tag_data): {e}")
        return None
    except Exception as e:
        print(f"Erro inesperado (extract_filtered_tag_data): {e}")
        return None


def process_files(
    files,
    tag_name,
    parent_tag=None,
    filter_tag=None,
    filter_value=None,
    filter_parent_path=None,
):
    """Processa arquivos XML para extração de tags, aplicando filtro se especificado."""
    results = []
    is_filtering = bool(parent_tag and filter_tag and filter_value)
    target_tag_name = tag_name

    for uploaded_file in files:
        file_name = getattr(uploaded_file, "name", str(uploaded_file))
        tag_data = None

        filter_description_parts = []
        if parent_tag:
            filter_description_parts.append(f"Contexto: {parent_tag}")
        if filter_tag:
            filter_description_parts.append(f"Tag Filtro: {filter_tag}")
        if filter_parent_path:
            filter_description_parts.append(f"Caminho Filtro: {filter_parent_path}")
        if filter_value:
            filter_description_parts.append(f"Valor Filtro: {filter_value}")
        filter_description = (
            ", ".join(filter_description_parts) if is_filtering else "Nenhum"
        )

        try:
            source_arg = None
            if hasattr(uploaded_file, "getvalue"):  # Trata UploadedFile do Streamlit
                uploaded_file.seek(0)
                source_arg = io.BytesIO(uploaded_file.getvalue())
            elif isinstance(uploaded_file, str) and os.path.exists(
                uploaded_file
            ):  # Trata caminho de arquivo
                source_arg = uploaded_file
            else:
                print(f"Fonte de arquivo inválida: {file_name}")
                results.append(
                    {
                        "Nome do Arquivo": file_name,
                        "TAG": target_tag_name,
                        "Filtro": filter_description,
                        "Valor": "[ARQUIVO INVÁLIDO]",
                        "Ocorrência": 0,
                    }
                )
                continue

            if is_filtering:
                tag_data = extract_filtered_tag_data(
                    source_arg,
                    parent_tag,
                    filter_tag,
                    filter_value,
                    target_tag_name,
                    filter_parent_path,
                )
            else:
                tag_data = extract_tag_data(source_arg, target_tag_name)

            if tag_data is not None:
                if not tag_data:
                    results.append(
                        {
                            "Nome do Arquivo": file_name,
                            "TAG": target_tag_name,
                            "Filtro": filter_description,
                            "Valor": "[NENHUM VALOR ENCONTRADO COM ESTES CRITÉRIOS]",
                            "Ocorrência": 0,
                        }
                    )
                else:
                    for value, count in tag_data.items():
                        results.append(
                            {
                                "Nome do Arquivo": file_name,
                                "TAG": target_tag_name,
                                "Filtro": filter_description,
                                "Valor": value,
                                "Ocorrência": count,
                            }
                        )
            else:
                results.append(
                    {
                        "Nome do Arquivo": file_name,
                        "TAG": target_tag_name,
                        "Filtro": filter_description,
                        "Valor": "[ERRO AO PROCESSAR XML]",
                        "Ocorrência": 0,
                    }
                )

        except Exception as e:
            print(f"Erro geral ao processar arquivo {file_name}: {e}")
            results.append(
                {
                    "Nome do Arquivo": file_name,
                    "TAG": target_tag_name,
                    "Filtro": filter_description,
                    "Valor": f"[ERRO INESPERADO: {str(e)}]",
                    "Ocorrência": 0,
                }
            )
        finally:
            if isinstance(source_arg, io.BytesIO):
                source_arg.close()
    return results


def consolidate_faturas_by_result(files, results, numero_lote):
    matching_fatura_strings = []
    fatura_count = 0
    target_tag = results[0]["TAG"]

    values_items_search = {
        item_dict["Valor"]: item_dict["Nome do Arquivo"]
        for item_dict in results
        if "Valor" in item_dict and "Nome do Arquivo" in item_dict
    }

    expected_values = set(values_items_search.keys())

    for uploaded_file in files:
        file_name = getattr(uploaded_file, "name", str(uploaded_file))
        print(f"Processando arquivo para consolidação: {file_name}")
        source_arg = None

        try:
            if hasattr(uploaded_file, "getvalue"):
                uploaded_file.seek(0)
                source_arg = io.BytesIO(uploaded_file.getvalue())
            elif isinstance(uploaded_file, str) and os.path.exists(uploaded_file):
                source_arg = uploaded_file
            else:
                print(f"  -> Fonte de arquivo inválida: {file_name}")
                continue

            context = etree.iterparse(
                source_arg, events=("end",), tag="Fatura", recover=True
            )
            for event, fatura_elem in context:
                # Busca direta pela tag
                target_text = fatura_elem.findtext(".//{*}" + target_tag)
                if target_text and target_text.strip().upper() in expected_values:
                    fatura_str = etree.tostring(
                        fatura_elem, encoding="unicode", pretty_print=True
                    )
                    matching_fatura_strings.append(fatura_str)
                    fatura_count += 1
                    print(f"  -> Fatura encontrada com {target_tag}={target_text}")

                # Liberação de memória
                fatura_elem.clear()
                while fatura_elem.getprevious() is not None:
                    del fatura_elem.getparent()[0]

            print(f"  -> Fim do processamento de {file_name} para consolidação")

        except etree.XMLSyntaxError as e:
            print(f"Erro de sintaxe XML no arquivo {file_name} (consolidação): {e}")
            continue
        except Exception as e:
            print(f"Erro inesperado ao processar {file_name} para consolidação: {e}")
            continue
        finally:
            if isinstance(source_arg, io.BytesIO):
                source_arg.close()

    # Consolida e formata o XML final
    data_criacao = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    if fatura_count > 0:
        xml_header = f'<loteNFCom NUMERO_LOTE="{numero_lote}" DATA_CRIACAO="{data_criacao}" QUANTIDADE_NFCOM_NO_LOTE="{fatura_count}">\n'
        xml_footer = "\n</loteNFCom>"
        consolidated_xml = xml_header + "\n".join(matching_fatura_strings) + xml_footer

        try:
            parser = etree.XMLParser(remove_blank_text=True)
            root = etree.fromstring(consolidated_xml.encode("utf-8"), parser)
            consolidated_xml = etree.tostring(
                root, pretty_print=True, encoding="unicode", xml_declaration=True
            )
        except Exception as indent_error:
            print(
                f"Erro ao tentar indentar XML consolidado: {indent_error}. Retornando não indentado."
            )
            if not consolidated_xml.strip().startswith("<?xml"):
                consolidated_xml = (
                    f"<?xml version='1.0' encoding='UTF-8'?>\n{consolidated_xml}"
                )

        return consolidated_xml, fatura_count

    else:
        print("Nenhuma Fatura encontrada com a UF especificada.")
        empty_lote_xml = f'<?xml version="1.0" encoding="UTF-8"?>\n<loteNFCom NUMERO_LOTE="{numero_lote}" DATA_CRIACAO="{data_criacao}" QUANTIDADE_NFCOM_NO_LOTE="0"></loteNFCom>'
        return empty_lote_xml, 0


def format_uf(value):
    """
    Formatador de UF, com base no código
    """
    ufs = {
        "11": "RO",
        "12": "AC",
        "16": "AP",
        "28": "SE",
        "29": "BA",
        "31": "MG",
        "32": "ES",
        "33": "RJ",
        "35": "SP",
        "41": "PR",
        "42": "SC",
        "43": "RS",
        "50": "MS",
        "51": "MT",
        "52": "GO",
        "53": "DF",
        "13": "AM",
        "14": "RR",
        "15": "PA",
        "17": "TO",
        "21": "MA",
        "22": "PI",
        "23": "CE",
        "24": "RN",
        "25": "PB",
        "26": "PE",
        "27": "AL",
    }

    if value in ufs:
        return ufs[value]

    return ""
