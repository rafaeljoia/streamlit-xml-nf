# -*- coding: utf-8 -*-
"""Módulo para processar arquivos XML grandes: extrair dados de tags (com filtro)
e consolidar blocos XML (Faturas) com base em filtro de UF."""

import os
from lxml import etree
from collections import Counter
import io
import datetime

# --- Funções de Extração de Tags (mantidas) ---

def extract_tag_data(xml_source, tag_name):
    """Processa XML e extrai valores/contagens de uma tag específica."""
    tag_values_counter = Counter()
    try:
        context = etree.iterparse(xml_source, events=("end",), tag=tag_name, recover=True)
        for event, elem in context:
            text_content = elem.text.strip() if elem.text else ""
            tag_values_counter[text_content] += 1
            elem.clear()
            while elem.getprevious() is not None:
                del elem.getparent()[0]
        return tag_values_counter
    except etree.XMLSyntaxError as e:
        print(f"Erro de sintaxe XML: {e}")
        return None
    except Exception as e:
        print(f"Erro inesperado (extract_tag_data): {e}")
        return None

def extract_filtered_tag_data(xml_source, common_ancestor_tag, filter_tag, filter_value, target_tag):
    """Processa XML, filtrando por valor de tag e extraindo outra tag sob o mesmo ancestral comum."""
    target_values_counter = Counter()
    try:
        context = etree.iterparse(xml_source, events=("end",), tag=common_ancestor_tag, recover=True)
        for event, ancestor_elem in context:
            filter_match = False
            target_value = None
            # Usar XPath para buscar em qualquer nível abaixo do ancestral
            filter_elem = ancestor_elem.xpath(f".//{filter_tag}")
            if filter_elem and filter_elem[0].text and filter_elem[0].text.strip() == filter_value:
                 filter_match = True

            if filter_match:
                target_elem = ancestor_elem.xpath(f".//{target_tag}")
                if target_elem and target_elem[0].text:
                    target_value = target_elem[0].text.strip()
                else:
                    target_value = "[TAG ALVO NÃO ENCONTRADA/VAZIA NO CONTEXTO]"
                target_values_counter[target_value] += 1

            ancestor_elem.clear()
            while ancestor_elem.getprevious() is not None:
                del ancestor_elem.getparent()[0]
        return target_values_counter
    except etree.XMLSyntaxError as e:
        print(f"Erro de sintaxe XML: {e}")
        return None
    except Exception as e:
        print(f"Erro inesperado (extract_filtered_tag_data): {e}")
        return None

def process_files(files, tag_name, parent_tag=None, filter_tag=None, filter_value=None):
    """Processa arquivos XML para extração de tags, aplicando filtro se especificado."""
    results = []
    is_filtering = bool(parent_tag and filter_tag and filter_value)
    target_tag_name = tag_name

    for uploaded_file in files:
        file_name = getattr(uploaded_file, 'name', str(uploaded_file))
        tag_data = None
        filter_description = f"{filter_tag}={filter_value} (contexto: {parent_tag})" if is_filtering else "Nenhum"

        try:
            source_arg = None
            if hasattr(uploaded_file, 'getvalue'):
                uploaded_file.seek(0)
                source_arg = io.BytesIO(uploaded_file.getvalue())
            elif isinstance(uploaded_file, str) and os.path.exists(uploaded_file):
                source_arg = uploaded_file
            else:
                print(f"Fonte de arquivo inválida: {file_name}")
                results.append({
                    'Nome do Arquivo': file_name, 'TAG': target_tag_name,
                    'Filtro': filter_description, 'Valor': '[ARQUIVO INVÁLIDO]', 'Ocorrência': 0
                })
                continue

            if is_filtering:
                tag_data = extract_filtered_tag_data(source_arg, parent_tag, filter_tag, filter_value, target_tag_name)
            else:
                tag_data = extract_tag_data(source_arg, target_tag_name)

            if tag_data is not None:
                if not tag_data:
                    results.append({
                        'Nome do Arquivo': file_name, 'TAG': target_tag_name,
                        'Filtro': filter_description, 'Valor': '[NENHUM VALOR ENCONTRADO COM ESTES CRITÉRIOS]', 'Ocorrência': 0
                    })
                else:
                    for value, count in tag_data.items():
                        results.append({
                            'Nome do Arquivo': file_name, 'TAG': target_tag_name,
                            'Filtro': filter_description, 'Valor': value, 'Ocorrência': count
                        })
            else:
                 results.append({
                     'Nome do Arquivo': file_name, 'TAG': target_tag_name,
                     'Filtro': filter_description, 'Valor': '[ERRO AO PROCESSAR XML]', 'Ocorrência': 0
                 })

        except Exception as e:
            print(f"Erro geral ao processar arquivo {file_name}: {e}")
            results.append({
                'Nome do Arquivo': file_name, 'TAG': target_tag_name,
                'Filtro': filter_description, 'Valor': '[ERRO INESPERADO NO PROCESSAMENTO]', 'Ocorrência': 0
            })
        finally:
            if isinstance(source_arg, io.BytesIO):
                source_arg.close()
    return results

# --- Nova Função de Consolidação --- 

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
    # Ajuste se a estrutura real for diferente
    uf_xpath = './/NFComVivo/NFComProc/NFCom/infNFCom/emit/enderEmit/UF'

    for uploaded_file in files:
        file_name = getattr(uploaded_file, 'name', str(uploaded_file))
        print(f"Processando arquivo para consolidação: {file_name}")
        source_arg = None
        try:
            if hasattr(uploaded_file, 'getvalue'):
                uploaded_file.seek(0)
                source_arg = io.BytesIO(uploaded_file.getvalue())
            elif isinstance(uploaded_file, str) and os.path.exists(uploaded_file):
                source_arg = uploaded_file
            else:
                print(f"  -> Fonte de arquivo inválida: {file_name}")
                continue

            # Iterar sobre os elementos <Fatura>
            context = etree.iterparse(source_arg, events=("end",), tag="Fatura", recover=True)
            for event, fatura_elem in context:
                # Verificar a UF dentro da Fatura atual
                uf_elements = fatura_elem.xpath(uf_xpath)
                if uf_elements and uf_elements[0].text and uf_elements[0].text.strip() == target_uf:
                    # Se a UF corresponder, serializar o elemento Fatura completo
                    # encoding='unicode' para obter string, tostring lida com namespaces se houver
                    fatura_str = etree.tostring(fatura_elem, encoding='unicode', pretty_print=True)
                    matching_fatura_strings.append(fatura_str)
                    fatura_count += 1
                    print(f"  -> Fatura encontrada com UF={target_uf}")
                
                # Limpeza de memória
                fatura_elem.clear()
                while fatura_elem.getprevious() is not None:
                    del fatura_elem.getparent()[0]
            
            print(f"  -> Fim do processamento de {file_name}")

        except etree.XMLSyntaxError as e:
            print(f"Erro de sintaxe XML no arquivo {file_name}: {e}")
            # Pode-se optar por continuar ou parar em caso de erro
            continue 
        except Exception as e:
            print(f"Erro inesperado ao processar {file_name} para consolidação: {e}")
            continue # Continua para o próximo arquivo
        finally:
             if isinstance(source_arg, io.BytesIO):
                source_arg.close()

    # Construir o XML final
    if fatura_count > 0:
        data_criacao = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        xml_header = f'<loteNFCom NUMERO_LOTE="{numero_lote}" DATA_CRIACAO="{data_criacao}" QUANTIDADE_NFCOM_NO_LOTE="{fatura_count}">\n'
        xml_footer = '\n</loteNFCom>'
        # Juntar o cabeçalho, todas as faturas encontradas e o rodapé
        consolidated_xml = xml_header + "\n".join(matching_fatura_strings) + xml_footer
        return consolidated_xml, fatura_count
    else:
        print("Nenhuma Fatura encontrada com a UF especificada.")
        return None, 0

# --- Bloco de Testes --- 
if __name__ == '__main__':
    # ... (testes anteriores de extração mantidos) ...

    # --- Testes para Consolidação --- 
    xml_fatura_test_1 = """
    <arquivo1>
        <Fatura ID_FATURA="A1">
            <NFComVivo><NFComProc><NFCom><infNFCom>
                <ide><cUF>35</cUF><nNF>001</nNF></ide>
                <emit><enderEmit><UF>SP</UF></enderEmit></emit>
            </infNFCom></NFCom></NFComProc></NFComVivo>
        </Fatura>
        <Fatura ID_FATURA="A2">
             <NFComVivo><NFComProc><NFCom><infNFCom>
                <ide><cUF>31</cUF><nNF>002</nNF></ide>
                <emit><enderEmit><UF>MG</UF></enderEmit></emit>
            </infNFCom></NFCom></NFComProc></NFComVivo>
        </Fatura>
    </arquivo1>
    """
    xml_fatura_test_2 = """
    <arquivo2>
        <Fatura ID_FATURA="B1">
            <NFComVivo><NFComProc><NFCom><infNFCom>
                <ide><cUF>35</cUF><nNF>003</nNF></ide>
                <emit><enderEmit><UF>SP</UF></enderEmit></emit>
            </infNFCom></NFCom></NFComProc></NFComVivo>
        </Fatura>
        <outraTag/>
        <Fatura ID_FATURA="B2">
             <NFComVivo><NFComProc><NFCom><infNFCom>
                <ide><cUF>35</cUF><nNF>004</nNF></ide>
                <emit><enderEmit><UF>SP</UF></enderEmit></emit>
            </infNFCom></NFCom></NFComProc></NFComVivo>
        </Fatura>
    </arquivo2>
    """
    with open("faturas1.xml", "w", encoding="utf-8") as f:
        f.write(xml_fatura_test_1)
    with open("faturas2.xml", "w", encoding="utf-8") as f:
        f.write(xml_fatura_test_2)

    print("\n--- Teste de Consolidação (UF=SP, Lote=999) ---")
    consolidated_xml_sp, count_sp = consolidate_faturas_by_uf(["faturas1.xml", "faturas2.xml"], target_uf="SP", numero_lote="999")
    if consolidated_xml_sp:
        print(f"Faturas encontradas para SP: {count_sp}")
        print("XML Consolidado (SP):")
        print(consolidated_xml_sp)
        # Salvar para verificar
        # with open("consolidado_sp.xml", "w", encoding="utf-8") as f:
        #     f.write(consolidated_xml_sp)
    else:
        print("Nenhuma fatura encontrada para SP.")

    print("\n--- Teste de Consolidação (UF=MG, Lote=888) ---")
    consolidated_xml_mg, count_mg = consolidate_faturas_by_uf(["faturas1.xml", "faturas2.xml"], target_uf="MG", numero_lote="888")
    if consolidated_xml_mg:
        print(f"Faturas encontradas para MG: {count_mg}")
        print("XML Consolidado (MG):")
        print(consolidated_xml_mg)
    else:
        print("Nenhuma fatura encontrada para MG.")

    print("\n--- Teste de Consolidação (UF=RJ, Lote=777) --- Nenhuma esperada")
    consolidated_xml_rj, count_rj = consolidate_faturas_by_uf(["faturas1.xml", "faturas2.xml"], target_uf="RJ", numero_lote="777")
    if consolidated_xml_rj:
        print(f"Faturas encontradas para RJ: {count_rj}")
    else:
        print("Nenhuma fatura encontrada para RJ (esperado).")

    # Limpar arquivos de teste
    # os.remove("faturas1.xml")
    # os.remove("faturas2.xml")
    # os.remove("exemplo_aninhado.xml") # Limpar teste anterior também

