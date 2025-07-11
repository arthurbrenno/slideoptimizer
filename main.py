import streamlit as st
import tempfile
import os
from pathlib import Path
from PIL import Image
import io
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.utils import ImageReader
import pdf2image
import subprocess
import platform

# Configuração da página do Streamlit
st.set_page_config(
    page_title="Otimizador de Slides PDF",
    page_icon="📄",
    layout="wide"
)

# Função para verificar e instalar poppler se necessário
def check_poppler():
    """Verifica se o poppler está instalado e tenta instalar se necessário."""
    try:
        # Tenta importar pdf2image e usar suas funções
        pdf2image.get_poppler_version()
        return True
    except Exception:
        st.warning("⚠️ Poppler não encontrado. Tentando instalar...")
        
        # Detecta o sistema operacional
        system = platform.system()
        
        try:
            if system == "Darwin":  # macOS
                # Verifica se o homebrew está instalado
                subprocess.run(["brew", "--version"], check=True, capture_output=True)
                # Instala poppler via homebrew
                subprocess.run(["brew", "install", "poppler"], check=True)
                st.success("✅ Poppler instalado com sucesso via Homebrew!")
                return True
            elif system == "Linux":
                # Para sistemas baseados em Debian/Ubuntu
                subprocess.run(["sudo", "apt-get", "update"], check=True)
                subprocess.run(["sudo", "apt-get", "install", "-y", "poppler-utils"], check=True)
                st.success("✅ Poppler instalado com sucesso!")
                return True
            else:
                st.error("❌ Sistema operacional não suportado para instalação automática do Poppler.")
                st.info("Por favor, instale o Poppler manualmente: https://poppler.freedesktop.org/")
                return False
        except subprocess.CalledProcessError:
            st.error("❌ Erro ao instalar Poppler. Por favor, instale manualmente.")
            if system == "Darwin":
                st.info("Para macOS: brew install poppler")
            elif system == "Linux":
                st.info("Para Linux: sudo apt-get install poppler-utils")
            return False

# Função para converter páginas PDF em imagens
def pdf_to_images(pdf_path, dpi=150):
    """Converte todas as páginas de um PDF em imagens."""
    try:
        images = pdf2image.convert_from_path(pdf_path, dpi=dpi)
        return images
    except Exception as e:
        st.error(f"Erro ao converter PDF em imagens: {str(e)}")
        return None

# Função para criar o PDF otimizado com 4 slides por página
def create_optimized_pdf(selected_images, output_path):
    """Cria um PDF com 4 slides por página em orientação horizontal (grid 2x2)."""
    # Dimensões da página A4 em landscape
    page_width, page_height = landscape(A4)
    
    # Margens
    margin = 30
    spacing = 20  # Espaço entre slides
    
    # Calcula as dimensões de cada slide na página
    # Largura: (largura_total - 2*margem - 1*espaçamento) / 2
    slide_width = (page_width - 2*margin - spacing) / 2
    # Altura: (altura_total - 2*margem - 1*espaçamento) / 2
    slide_height = (page_height - 2*margin - spacing) / 2
    
    # Cria o canvas do PDF
    c = canvas.Canvas(output_path, pagesize=landscape(A4))
    
    # Processa as imagens selecionadas em grupos de 4
    for page_idx in range(0, len(selected_images), 4):
        # Define as posições dos 4 slides (origem no canto inferior esquerdo)
        # Grid 2x2: [0,1] na linha superior, [2,3] na linha inferior
        positions = []
        
        # Linha superior (y mais alto)
        y_top = margin + slide_height + spacing
        # Slide superior esquerdo (posição 0)
        positions.append((margin, y_top))
        # Slide superior direito (posição 1)
        positions.append((margin + slide_width + spacing, y_top))
        
        # Linha inferior (y mais baixo)
        y_bottom = margin
        # Slide inferior esquerdo (posição 2)
        positions.append((margin, y_bottom))
        # Slide inferior direito (posição 3)
        positions.append((margin + slide_width + spacing, y_bottom))
        
        # Adiciona até 4 slides na página atual
        for j in range(4):
            if page_idx + j < len(selected_images):
                img = selected_images[page_idx + j]
                
                # Converte PIL Image para formato compatível com reportlab
                img_buffer = io.BytesIO()
                # Salva com qualidade alta
                img.save(img_buffer, format='PNG', optimize=True)
                img_buffer.seek(0)
                
                # Calcula o tamanho para manter a proporção
                img_width, img_height = img.size
                aspect_ratio = img_width / img_height
                
                # Ajusta dimensões mantendo proporção
                if aspect_ratio > slide_width / slide_height:
                    # Imagem é mais larga que o espaço
                    draw_width = slide_width
                    draw_height = slide_width / aspect_ratio
                else:
                    # Imagem é mais alta que o espaço
                    draw_height = slide_height
                    draw_width = slide_height * aspect_ratio
                
                # Centraliza a imagem no espaço do slide
                x_offset = (slide_width - draw_width) / 2
                y_offset = (slide_height - draw_height) / 2
                
                # Pega a posição base
                x_base, y_base = positions[j]
                
                # Calcula posição final centralizada
                x_final = x_base + x_offset
                y_final = y_base + y_offset
                
                # Desenha uma borda fina ao redor do slide (opcional)
                c.setStrokeColorRGB(0.8, 0.8, 0.8)
                c.setLineWidth(0.5)
                c.rect(x_base, y_base, slide_width, slide_height)
                
                # Desenha a imagem
                c.drawImage(
                    ImageReader(img_buffer),
                    x_final,
                    y_final,
                    width=draw_width,
                    height=draw_height,
                    preserveAspectRatio=True,
                    mask='auto'
                )
                
                # Adiciona número do slide no canto inferior esquerdo
                c.setFont("Helvetica", 10)
                c.setFillColorRGB(0.3, 0.3, 0.3)
                c.drawString(x_base + 5, y_base + 5, f"Slide {page_idx + j + 1}")
        
        # Nova página se houver mais slides
        if page_idx + 4 < len(selected_images):
            c.showPage()
    
    # Salva o PDF
    c.save()

# Interface principal do Streamlit
def main():
    st.title("📄 Otimizador de Slides PDF")
    st.markdown("""
    Este aplicativo permite otimizar a impressão de slides de apresentações em PDF,
    organizando **4 slides por página** em orientação horizontal (layout 2x2) para economizar papel.
    
    **Layout final:** 2 slides na linha superior + 2 slides na linha inferior = 4 slides por página A4
    """)
    
    # Verifica se o poppler está instalado
    if not check_poppler():
        st.stop()
    
    # Upload do arquivo PDF
    uploaded_file = st.file_uploader(
        "Escolha um arquivo PDF",
        type=['pdf'],
        help="Selecione o arquivo PDF que contém os slides"
    )
    
    if uploaded_file is not None:
        # Salva o arquivo temporariamente
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
            tmp_file.write(uploaded_file.getvalue())
            tmp_path = tmp_file.name
        
        try:
            # Converte PDF em imagens
            with st.spinner("Processando PDF... Isso pode levar alguns segundos."):
                images = pdf_to_images(tmp_path)
            
            if images:
                st.success(f"✅ PDF carregado com sucesso! Total de {len(images)} páginas.")
                
                # Seção de seleção de páginas
                st.markdown("### 📑 Selecione as páginas para incluir no PDF otimizado")
                
                # Botões de seleção rápida
                col1, col2, col3 = st.columns(3)
                with col1:
                    if st.button("✅ Selecionar Todas"):
                        st.session_state.selected_pages = list(range(len(images)))
                with col2:
                    if st.button("❌ Desmarcar Todas"):
                        st.session_state.selected_pages = []
                with col3:
                    if st.button("🔄 Inverter Seleção"):
                        current = st.session_state.get('selected_pages', [])
                        st.session_state.selected_pages = [i for i in range(len(images)) if i not in current]
                
                # Inicializa a seleção se não existir
                if 'selected_pages' not in st.session_state:
                    st.session_state.selected_pages = list(range(len(images)))
                
                # Grade de visualização com checkboxes
                cols_per_row = 4
                rows = (len(images) + cols_per_row - 1) // cols_per_row
                
                selected_indices = []
                
                for row in range(rows):
                    cols = st.columns(cols_per_row)
                    for col_idx in range(cols_per_row):
                        page_idx = row * cols_per_row + col_idx
                        if page_idx < len(images):
                            with cols[col_idx]:
                                # Redimensiona a imagem para visualização
                                img = images[page_idx]
                                img_resized = img.copy()
                                img_resized.thumbnail((300, 300), Image.Resampling.LANCZOS)
                                
                                # Mostra a imagem
                                st.image(img_resized, use_container_width=True)
                                
                                # Checkbox para seleção
                                is_selected = st.checkbox(
                                    f"Página {page_idx + 1}",
                                    value=page_idx in st.session_state.selected_pages,
                                    key=f"page_{page_idx}"
                                )
                                
                                if is_selected:
                                    selected_indices.append(page_idx)
                
                # Atualiza as páginas selecionadas
                st.session_state.selected_pages = selected_indices
                
                # Mostra contador de páginas selecionadas
                st.info(f"📊 {len(selected_indices)} páginas selecionadas de {len(images)} total")
                
                # Botão para gerar PDF otimizado
                if st.button("🚀 Gerar PDF Otimizado", type="primary", disabled=len(selected_indices) == 0):
                    if selected_indices:
                        with st.spinner("Gerando PDF otimizado..."):
                            # Filtra apenas as imagens selecionadas
                            selected_images = [images[i] for i in sorted(selected_indices)]
                            
                            # Cria o PDF otimizado
                            output_path = tempfile.mktemp(suffix='.pdf')
                            create_optimized_pdf(selected_images, output_path)
                            
                            # Lê o arquivo gerado
                            with open(output_path, 'rb') as f:
                                pdf_data = f.read()
                            
                            # Calcula estatísticas
                            total_pages_original = len(selected_indices)
                            total_pages_optimized = (total_pages_original + 3) // 4
                            
                            st.success(f"""
                            ✅ PDF otimizado gerado com sucesso!
                            - Páginas originais selecionadas: {total_pages_original}
                            - Páginas no PDF otimizado: {total_pages_optimized}
                            - Slides por página: 4 (layout 2x2)
                            - Economia de papel: {((total_pages_original - total_pages_optimized) / total_pages_original * 100):.1f}%
                            """)
                            
                            # Botão de download
                            st.download_button(
                                label="📥 Baixar PDF Otimizado",
                                data=pdf_data,
                                file_name=f"slides_otimizados_{uploaded_file.name}",
                                mime="application/pdf"
                            )
                            
                            # Limpa o arquivo temporário
                            os.unlink(output_path)
                    else:
                        st.warning("⚠️ Por favor, selecione pelo menos uma página.")
                
        except Exception as e:
            st.error(f"❌ Erro ao processar o PDF: {str(e)}")
            st.info("Verifique se o arquivo PDF não está corrompido e tente novamente.")
        
        finally:
            # Limpa o arquivo temporário
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
    
    # Instruções de uso
    with st.expander("ℹ️ Como usar este aplicativo"):
        st.markdown("""
        1. **Faça upload do seu PDF** usando o botão acima
        2. **Visualize todas as páginas** do documento
        3. **Selecione as páginas** que deseja incluir no PDF otimizado
        4. **Clique em "Gerar PDF Otimizado"** para criar o novo arquivo
        5. **Baixe o PDF** com 4 slides por página em orientação horizontal
        
        **Layout do PDF otimizado:**
        - Página em orientação paisagem (horizontal)
        - Grid 2x2: 4 slides por página A4
        - 2 slides na linha superior
        - 2 slides na linha inferior
        - Bordas finas para delimitar cada slide
        - Numeração dos slides preservada
        
        **Dicas:**
        - Use os botões de seleção rápida para marcar/desmarcar várias páginas
        - O layout 2x2 horizontal é ideal para impressão e leitura
        - Cada página do PDF final conterá exatamente 4 slides originais
        - Economia de até 75% de papel comparado à impressão de 1 slide por página
        """)

if __name__ == "__main__":
    main()