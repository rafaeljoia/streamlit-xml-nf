# -*- coding: utf-8 -*-
"""Módulo para processar arquivos XML grandes: extrair dados de tags (com filtro)
e consolidar blocos XML (Faturas) com base em filtro de UF."""

import os
from lxml import etree
from collections import Counter
import io
import datetime

# --- Funções de Extração de Tags ---


def extract_tag_data(xml_source, tag_name):
    """Processa XML e extrai valores/contagens de uma tag específica."""
    tag_values_counter = Counter()
    try:
        # Adicionar recover=True para tentar lidar com XMLs malformados
        context = etree.iterparse(
            xml_source, events=("end",), tag=tag_name, recover=True
        )
        for event, elem in context:
            text_content = elem.text.strip() if elem.text else ""
            tag_values_counter[text_content] += 1
            elem.clear()
            # Otimização para limpar elementos processados da árvore
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
    """Processa XML, filtrando por valor de tag e extraindo outra tag sob o mesmo ancestral comum.
    Permite especificar um caminho para o pai da tag de filtro.
    """
    target_values_counter = Counter()
    try:
        context = etree.iterparse(
            xml_source, events=("end",), tag=common_ancestor_tag, recover=True
        )
        for event, ancestor_elem in context:
            filter_match = False
            target_value_found_in_context = None  # Renomeado para clareza

            # Constrói o XPath para a tag de filtro
            xpath_filter_tag = filter_tag
            if filter_parent_path:
                # Garante que o caminho não comece ou termine com / e junta com filter_tag
                clean_path = "/".join(
                    p for p in filter_parent_path.strip("/").split("/") if p
                )
                if clean_path:  # Se o caminho não for vazio após limpeza
                    xpath_filter_tag = f"{clean_path}/{filter_tag}"
                # Se clean_path for vazio (ex: "/"), usa apenas filter_tag relativo ao ancestor

            # Busca o elemento de filtro usando o XPath construído (relativo ao ancestor_elem)
            # O ponto no início do XPath (./) o torna relativo ao nó atual (ancestor_elem)
            filter_elements = ancestor_elem.xpath(f"./{xpath_filter_tag}")

            if not filter_elements and not filter_parent_path:
                # Fallback para a lógica original se filter_parent_path não foi fornecido e a busca direta falhou
                # (ou se o usuário quer buscar em qualquer nível abaixo do ancestral sem especificar caminho)
                filter_elements = ancestor_elem.xpath(f".//{filter_tag}")

            for (
                filter_elem_item
            ) in filter_elements:  # Itera sobre os elementos encontrados
                if (
                    filter_elem_item.text
                    and filter_elem_item.text.strip() == filter_value
                ):
                    filter_match = True
                    break  # Encontrou um match, não precisa checar outros

            if filter_match:
                # Busca a tag alvo em qualquer nível abaixo do ancestral comum
                target_elements = ancestor_elem.xpath(f".//{target_tag}")
                if target_elements and target_elements[0].text:
                    target_value_found_in_context = target_elements[0].text.strip()
                else:
                    target_value_found_in_context = (
                        "[TAG ALVO NÃO ENCONTRADA/VAZIA NO CONTEXTO DO FILTRO]"
                    )
                target_values_counter[target_value_found_in_context] += 1

            ancestor_elem.clear()
            while ancestor_elem.getprevious() is not None:
                del ancestor_elem.getparent()[0]
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
            else:  # Erro no processamento do XML (ex: sintaxe)
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


# --- Função de Consolidação (sem alterações nesta etapa) ---


def consolidate_faturas_by_uf(files, target_uf, numero_lote):
    """Consolida blocos <Fatura> de múltiplos arquivos XML filtrando por UF.
    Args:
        files: Lista de UploadedFile ou caminhos de arquivo.
        target_uf: O valor da tag UF para filtrar (ex: "SP").
        numero_lote: O número do lote fornecido pelo usuário.
    Returns:
        Uma tupla: (string_xml_consolidado, contagem_faturas) ou (None, 0) em caso de erro.
    """
    matching_fatura_strings = []
    fatura_count = 0
    # Caminho XPath para encontrar a UF dentro da Fatura, baseado no exemplo do usuário
    # Ajuste se a estrutura real for diferente. Idealmente, isso seria parametrizável.
    # Para o exemplo fornecido pelo usuário, a UF está em <infNFCom><emit><enderEmit><UF>
    # Se a tag <Fatura> é o elemento iterado, o XPath relativo seria:
    uf_xpath_options = [
        ".//infNFCom/emit/enderEmit/UF",  # Caminho comum em NFCom dentro de Fatura
        ".//emit/enderEmit/UF",  # Se Fatura já for infNFCom ou similar
        ".//dest/enderDest/UF",  # Outro local comum para UF
        ".//UF",  # Busca genérica, menos precisa
    ]

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

            # Iterar sobre os elementos <Fatura> (ou o nome da tag que representa a fatura)
            # O usuário mencionou <Fatura>, então vamos usar isso.
            context = etree.iterparse(
                source_arg, events=("end",), tag="Fatura", recover=True
            )
            for event, fatura_elem in context:
                uf_found_in_fatura = False
                for xpath_opt in uf_xpath_options:
                    uf_elements = fatura_elem.xpath(xpath_opt)
                    if (
                        uf_elements
                        and uf_elements[0].text
                        and uf_elements[0].text.strip().upper() == target_uf.upper()
                    ):
                        fatura_str = etree.tostring(
                            fatura_elem, encoding="unicode", pretty_print=True
                        )
                        matching_fatura_strings.append(fatura_str)
                        fatura_count += 1
                        uf_found_in_fatura = True
                        print(
                            f"  -> Fatura encontrada com UF={target_uf} via {xpath_opt}"
                        )
                        break  # UF encontrada para esta fatura

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

    if fatura_count > 0:
        data_criacao = datetime.datetime.now().strftime(
            "%Y-%m-%dT%H:%M:%S"
        )  # Formato ISO
        # Usar um nome de lote raiz mais genérico, como <loteDocumentos> ou <loteFaturas>
        # O usuário pediu <loteNFCom>
        xml_header = f'<loteNFCom NUMERO_LOTE="{numero_lote}" DATA_CRIACAO="{data_criacao}" QUANTIDADE_NFCOM_NO_LOTE="{fatura_count}">\n'
        xml_footer = "\n</loteNFCom>"
        consolidated_xml = xml_header + "\n".join(matching_fatura_strings) + xml_footer

        # Tentar indentar o XML final para melhor leitura
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
            # Se a indentação falhar, retorna o XML como está, mas com declaração XML
            if not consolidated_xml.strip().startswith("<?xml"):
                consolidated_xml = (
                    f"<?xml version='1.0' encoding='UTF-8'?>\n{consolidated_xml}"
                )

        return consolidated_xml, fatura_count
    else:
        print("Nenhuma Fatura encontrada com a UF especificada.")
        # Retorna um XML vazio de lote se nada for encontrado, para consistência
        data_criacao = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        empty_lote_xml = f'<?xml version="1.0" encoding="UTF-8"?>\n<loteNFCom NUMERO_LOTE="{numero_lote}" DATA_CRIACAO="{data_criacao}" QUANTIDADE_NFCOM_NO_LOTE="0"></loteNFCom>'
        return empty_lote_xml, 0


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


# --- Bloco de Testes (pode ser expandido) ---
if __name__ == "__main__":
    # Exemplo de XML para teste de extração com caminho de filtro
    xml_content_test_filtro_profundo = """
    <documento>
        <infNFCom id="1">
            <ide>
                <nNF>1001</nNF>
            </ide>
            <dest>
                <xNome>CLUBE DE CAMPO MOEMA</xNome>
                <enderDest>
                    <UF>SP</UF>
                </enderDest>
            </dest>
            <outro>
                <xNome>NAO FILTRAR ESTE</xNome>
            </outro>
        </infNFCom>
        <infNFCom id="2">
            <ide>
                <nNF>1002</nNF>
            </ide>
            <dest>
                <xNome>OUTRO CLIENTE</xNome>
                <enderDest>
                    <UF>RJ</UF>
                </enderDest>
            </dest>
        </infNFCom>
        <infNFCom id="3">
            <ide>
                <nNF>1003</nNF>
            </ide>
            <dest>
                 <!-- xNome ausente aqui -->
                <enderDest>
                    <UF>SP</UF>
                </enderDest>
            </dest>
        </infNFCom>
         <infNFCom id="4">
            <ide>
                <nNF>1004</nNF>
            </ide>
            <dest>
                <xNome>CLUBE DE CAMPO MOEMA</xNome> <!-- Outro para o mesmo cliente -->
                <enderDest>
                    <UF>MG</UF>
                </enderDest>
            </dest>
        </infNFCom>
    </documento>
    """
    with open("test_filtro_profundo.xml", "w", encoding="utf-8") as f:
        f.write(xml_content_test_filtro_profundo)

    print("--- Teste de Extração com Filtro Profundo ---")
    # Cenário: Extrair nNF onde dest/xNome é CLUBE DE CAMPO MOEMA, dentro de infNFCom
    results_profundo = process_files(
        files=["test_filtro_profundo.xml"],
        tag_name="nNF",
        parent_tag="infNFCom",
        filter_tag="xNome",
        filter_value="CLUBE DE CAMPO MOEMA",
        filter_parent_path="dest",  # Novo parâmetro
    )
    print("Resultados (Filtro Profundo: dest/xNome = CLUBE DE CAMPO MOEMA, Alvo: nNF):")
    for r in results_profundo:
        print(r)
    # Esperado: nNF 1001 e 1004

    print("\n--- Teste de Extração com Filtro Profundo (Caminho Inválido) ---")
    results_profundo_err = process_files(
        files=["test_filtro_profundo.xml"],
        tag_name="nNF",
        parent_tag="infNFCom",
        filter_tag="xNome",
        filter_value="CLUBE DE CAMPO MOEMA",
        filter_parent_path="caminho/inexistente",
    )
    print("Resultados (Filtro Profundo Caminho Inválido):")
    for r in results_profundo_err:
        print(r)
    # Esperado: Nenhum resultado ou mensagem de erro apropriada

    print("\n--- Teste de Extração com Filtro (Sem Caminho - Fallback) ---")
    # Deve pegar xNome em qualquer lugar sob infNFCom
    results_fallback = process_files(
        files=["test_filtro_profundo.xml"],
        tag_name="nNF",
        parent_tag="infNFCom",
        filter_tag="xNome",
        filter_value="NAO FILTRAR ESTE",
        filter_parent_path=None,  # Ou omitido
    )
    print("Resultados (Filtro Fallback: xNome = NAO FILTRAR ESTE, Alvo: nNF):")
    for r in results_fallback:
        print(r)
    # Esperado: nNF 1001 (porque <outro><xNome>NAO FILTRAR ESTE</xNome> está sob infNFCom id=1)

    # Limpar arquivo de teste
    if os.path.exists("test_filtro_profundo.xml"):
        os.remove("test_filtro_profundo.xml")

    # ... (testes de consolidação podem ser mantidos ou adaptados aqui) ...
    # Exemplo: criar arquivos faturas1.xml e faturas2.xml como no original para testar consolidação
    xml_fatura_test_1 = """..."""  # Conteúdo original omitido para brevidade
    xml_fatura_test_2 = """..."""  # Conteúdo original omitido para brevidade
    # with open("faturas1.xml", "w", encoding="utf-8") as f: f.write(xml_fatura_test_1)
    # with open("faturas2.xml", "w", encoding="utf-8") as f: f.write(xml_fatura_test_2)
    # ... resto dos testes de consolidação ...
    # if os.path.exists("faturas1.xml"): os.remove("faturas1.xml")
    # if os.path.exists("faturas2.xml"): os.remove("faturas2.xml")
