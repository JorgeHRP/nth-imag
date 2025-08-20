import base64
import io
from fastapi import FastAPI
from pydantic import BaseModel
from PIL import Image, ImageDraw, ImageFont

app = FastAPI()

# === Modelo da requisição ===
class RequestData(BaseModel):
    imagem_base64: str
    logo_base64: str
    texto: str

# === Função principal ===
def gerar_imagem_final(
    imagem: Image.Image,
    overlay: Image.Image,
    texto: str,
    fonte_path="arialbd.ttf",
    tamanho_fonte=60,
    cor_texto=(255, 255, 255),
    margem_porcento=0.10
):
    # --- 1. Recorte 4x5 ---
    largura, altura = imagem.size
    proporcao_desejada = 5 / 4
    altura_corte = int(largura * proporcao_desejada)

    if altura_corte <= altura:
        top = (altura - altura_corte) // 2
        bottom = top + altura_corte
        left, right = 0, largura
    else:
        largura_corte = int(altura * 4 / 5)
        left = (largura - largura_corte) // 2
        right = left + largura_corte
        top, bottom = 0, altura

    imagem = imagem.crop((left, top, right, bottom)).convert("RGBA")

    # --- 2. Aplicar máscara degradê ---
    for _ in range(3):
        largura, altura = imagem.size
        mascara = Image.new("RGBA", (largura, altura), (0, 0, 0, 0))
        draw = ImageDraw.Draw(mascara)

        degradê_inicio = int(altura * 0.6)
        degradê_fim = altura
        alpha_inicio = 0
        alpha_fim = 200

        for y in range(degradê_inicio, degradê_fim):
            progress = (y - degradê_inicio) / (degradê_fim - degradê_inicio)
            alpha = int(alpha_inicio + (alpha_fim - alpha_inicio) * progress)
            draw.line([(0, y), (largura, y)], fill=(0, 0, 0, alpha))

        imagem = Image.alpha_composite(imagem, mascara)

    # --- 3. Sobrepor logo ---
    largura_desejada = imagem.width // 3
    proporcao = largura_desejada / overlay.width
    altura_desejada = int(overlay.height * proporcao)
    overlay_resized = overlay.resize((largura_desejada, altura_desejada), resample=Image.Resampling.LANCZOS).convert("RGBA")

    x = (imagem.width - overlay_resized.width) // 2
    y = int(imagem.height * 2 / 3) - (overlay_resized.height // 2)

    # usar paste para evitar erro de tamanhos diferentes
    imagem.paste(overlay_resized, (x, y), overlay_resized)

    # --- 4. Adicionar texto ---
    draw = ImageDraw.Draw(imagem)
    largura, altura = imagem.size
    margem_lateral = int(largura * margem_porcento)
    margem_vertical = int(altura * margem_porcento)
    largura_util = largura - 2 * margem_lateral

    y_topo = int(altura * 0.65) + margem_vertical
    y_base = altura - margem_vertical
    altura_util = y_base - y_topo

    def quebrar_texto(draw, texto, fonte, largura_max):
        palavras, linhas, linha_atual = texto.split(), [], ""
        for palavra in palavras:
            nova = linha_atual + " " + palavra if linha_atual else palavra
            if draw.textlength(nova, font=fonte) <= largura_max:
                linha_atual = nova
            else:
                if linha_atual:
                    linhas.append(linha_atual)
                linha_atual = palavra
        if linha_atual:
            linhas.append(linha_atual)
        return linhas

    fonte_tentativa = tamanho_fonte
    while fonte_tentativa >= 10:
        fonte = ImageFont.truetype(fonte_path, fonte_tentativa)
        linhas = quebrar_texto(draw, texto, fonte, largura_util)
        altura_linha = fonte.getbbox("Ag")[3]
        altura_total = altura_linha * len(linhas)
        if altura_total <= altura_util:
            break
        fonte_tentativa -= 1

    fonte = ImageFont.truetype(fonte_path, fonte_tentativa)
    linhas = quebrar_texto(draw, texto, fonte, largura_util)
    altura_linha = fonte.getbbox("Ag")[3]
    y = y_topo + (altura_util - altura_linha * len(linhas)) // 2

    for linha in linhas:
        largura_texto = draw.textlength(linha, font=fonte)
        x = (largura - largura_texto) // 2
        sombra_offset = 2
        sombra_cor = (0, 0, 0, 100)
        draw.text((x + sombra_offset, y + sombra_offset), linha, font=fonte, fill=sombra_cor)
        for dx, dy in [(-1,0),(1,0),(0,-1),(0,1)]:
            draw.text((x+dx, y+dy), linha, font=fonte, fill=(0,0,0))
        draw.text((x, y), linha, font=fonte, fill=cor_texto)
        y += altura_linha

    # --- 5. Converter para base64 ---
    buffer = io.BytesIO()
    imagem.convert("RGB").save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("utf-8")

# === Helper para limpar base64 (aceita data:image/...;base64, ou só o conteúdo) ===
def limpar_base64(data_uri: str) -> str:
    if "," in data_uri:
        return data_uri.split(",")[1]
    return data_uri

# === Endpoint ===
@app.post("/gerar_imagem")
def processar(dados: RequestData):
    imagem_bytes = base64.b64decode(limpar_base64(dados.imagem_base64))
    logo_bytes = base64.b64decode(limpar_base64(dados.logo_base64))

    imagem = Image.open(io.BytesIO(imagem_bytes))
    logo = Image.open(io.BytesIO(logo_bytes))

    imagem_final_b64 = gerar_imagem_final(imagem, logo, dados.texto)
    return {"imagem_base64": imagem_final_b64}
