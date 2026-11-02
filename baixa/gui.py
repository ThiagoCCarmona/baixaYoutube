"""Interface gráfica (CustomTkinter) do baixa."""

import logging
import logging.handlers
import os
import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk

from baixa import __version__, atualizador
from baixa.erros import ErroDownload
from baixa.dados import ARQUIVO_LOG, PASTA_DADOS, carregar_config, salvar_config

# O núcleo (yt-dlp) é pesado: é importado em segundo plano depois que a janela aparece.

# Cores (claro, escuro)
VERMELHO = ("#e5252a", "#ff3b3f")
VERMELHO_HOVER = ("#c41d22", "#e0282c")
FUNDO = ("#f4f5f7", "#121214")
CARTAO = ("#ffffff", "#1c1c1f")
BORDA = ("#e3e4e8", "#2c2c31")
TEXTO = ("#1c1c1f", "#f4f5f7")
TEXTO_SUAVE = ("#6b6f78", "#9a9ca3")
VERDE = ("#1a9c55", "#3ccf7a")
AZUL_FUNDO = ("#e8f0fe", "#1a2433")
AZUL = ("#1a5fd0", "#7fb0ff")

log = logging.getLogger("baixa.gui")


class App(ctk.CTk):
    def __init__(self):
        super().__init__(fg_color=FUNDO)
        self.title("baixa")
        self.geometry("620x720")
        self.minsize(420, 700)

        self.eventos: queue.Queue = queue.Queue()
        self.ultimo_arquivo: Path | None = None
        self.baixando = False
        self.recarregar_motor_pendente = False
        self.nova_versao: atualizador.NovaVersao | None = None

        config = carregar_config()
        self.formato = ctk.StringVar(value=config.get("formato", "mp3").upper())
        self.pasta = ctk.StringVar(value=config.get("pasta") or str(Path.home() / "Downloads"))
        self.maxima = ctk.BooleanVar(value=config.get("qualidade") == "maxima")

        self.fonte_titulo = ctk.CTkFont(size=24, weight="bold")
        self.fonte_rotulo = ctk.CTkFont(size=13, weight="bold")
        self.fonte = ctk.CTkFont(size=14)
        self.fonte_pequena = ctk.CTkFont(size=12)

        self._montar()
        self.bind("<Return>", lambda _: self._iniciar())
        self.after(100, self._processar_eventos)
        self.after(200, self._precarregar)
        self.after(1500, lambda: threading.Thread(target=self._verificar_atualizacoes, daemon=True).start())

    def report_callback_exception(self, tipo, valor, rastro):
        log.error("Erro na interface", exc_info=(tipo, valor, rastro))

    @staticmethod
    def _precarregar() -> None:
        threading.Thread(target=lambda: __import__("baixa.nucleo"), daemon=True).start()

    # ---------- layout ----------

    def _montar(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        cabecalho = ctk.CTkFrame(self, fg_color="transparent")
        cabecalho.grid(row=0, column=0, sticky="ew", padx=28, pady=(24, 12))
        ctk.CTkLabel(
            cabecalho, text="▶", font=ctk.CTkFont(size=20), text_color="white",
            fg_color=VERMELHO, corner_radius=10, width=40, height=40,
        ).pack(side="left")
        textos = ctk.CTkFrame(cabecalho, fg_color="transparent")
        textos.pack(side="left", padx=12)
        ctk.CTkLabel(textos, text="baixa", font=self.fonte_titulo).pack(anchor="w")
        ctk.CTkLabel(
            textos, text="YouTube para MP3 ou MP4", font=self.fonte_pequena, text_color=TEXTO_SUAVE
        ).pack(anchor="w")
        self.rotulo_versao = ctk.CTkLabel(
            cabecalho, text="", font=self.fonte_pequena, text_color=TEXTO_SUAVE, justify="right"
        )
        self.rotulo_versao.pack(side="right", anchor="n")
        self._atualizar_rotulo_versao()

        # Faixa de atualização (aparece só quando há versão nova)
        self.faixa = ctk.CTkFrame(self, fg_color=AZUL_FUNDO, corner_radius=12)
        self.faixa.grid_columnconfigure(0, weight=1)
        self.texto_faixa = ctk.CTkLabel(
            self.faixa, text="", font=self.fonte_pequena, text_color=AZUL, anchor="w", justify="left"
        )
        self.texto_faixa.grid(row=0, column=0, sticky="ew", padx=(14, 8), pady=10)
        self.botao_atualizar = ctk.CTkButton(
            self.faixa, text="Atualizar agora", command=self._instalar_atualizacao,
            width=130, height=32, corner_radius=8, font=self.fonte_rotulo,
            fg_color=AZUL, hover_color=("#164fae", "#6a9ee8"), text_color=("white", "#0f1620"),
        )
        self.botao_atualizar.grid(row=0, column=1, padx=(0, 10), pady=8)

        cartao = ctk.CTkFrame(
            self, fg_color=CARTAO, corner_radius=16, border_width=1, border_color=BORDA
        )
        cartao.grid(row=2, column=0, sticky="nsew", padx=24, pady=(0, 24))
        cartao.grid_columnconfigure(0, weight=1)

        # Link
        self._rotulo(cartao, "Link do vídeo", 0)
        linha_link = ctk.CTkFrame(cartao, fg_color="transparent")
        linha_link.grid(row=1, column=0, sticky="ew", padx=20)
        linha_link.grid_columnconfigure(0, weight=1)
        self.campo_link = self._entrada(linha_link, "https://www.youtube.com/watch?v=...")
        self.campo_link.grid(row=0, column=0, sticky="ew")
        self.botao_colar = self._botao_secundario(linha_link, "Colar", self._colar)
        self.botao_colar.grid(row=0, column=1, padx=(8, 0))

        # Nome
        self._rotulo(cartao, "Nome do arquivo", 2)
        self.campo_nome = self._entrada(cartao, "Opcional — vazio usa o título do vídeo")
        self.campo_nome.grid(row=3, column=0, sticky="ew", padx=20)

        # Formato
        self._rotulo(cartao, "Formato", 4)
        linha_formato = ctk.CTkFrame(cartao, fg_color="transparent")
        linha_formato.grid(row=5, column=0, sticky="ew", padx=20)
        linha_formato.grid_columnconfigure((0, 1), weight=1, uniform="formato")
        self.botoes_formato = {}
        for i, (valor, descricao) in enumerate((("MP3", "MP3 · áudio"), ("MP4", "MP4 · vídeo"))):
            botao = ctk.CTkButton(
                linha_formato, text=descricao, height=40, corner_radius=10,
                font=self.fonte_rotulo, command=lambda v=valor: self._escolher_formato(v),
            )
            botao.grid(row=0, column=i, sticky="ew", padx=(0, 4) if i == 0 else (4, 0))
            self.botoes_formato[valor] = botao
        self.chave_maxima = ctk.CTkSwitch(
            linha_formato, text="Qualidade máxima (até 4K/8K — pode não abrir em players antigos)",
            variable=self.maxima, font=self.fonte_pequena, progress_color=VERMELHO,
            text_color=TEXTO, text_color_disabled=TEXTO_SUAVE,
        )
        self.chave_maxima.grid(row=1, column=0, columnspan=2, sticky="w", pady=(10, 0))
        self._escolher_formato(self.formato.get())

        # Pasta
        self._rotulo(cartao, "Salvar em", 6)
        linha_pasta = ctk.CTkFrame(cartao, fg_color="transparent")
        linha_pasta.grid(row=7, column=0, sticky="ew", padx=20)
        linha_pasta.grid_columnconfigure(0, weight=1)
        self.campo_pasta = self._entrada(linha_pasta, "", textvariable=self.pasta)
        self.campo_pasta.grid(row=0, column=0, sticky="ew")
        self.botao_pasta = self._botao_secundario(linha_pasta, "Escolher", self._escolher_pasta)
        self.botao_pasta.grid(row=0, column=1, padx=(8, 0))

        # Espaço flexível: o cartão estica, os controles ficam no topo e a ação embaixo
        cartao.grid_rowconfigure(8, weight=1, minsize=20)

        self.botao_baixar = ctk.CTkButton(
            cartao, text="Baixar", command=self._iniciar, height=48, corner_radius=12,
            font=ctk.CTkFont(size=16, weight="bold"),
            fg_color=VERMELHO, hover_color=VERMELHO_HOVER,
        )
        self.botao_baixar.grid(row=9, column=0, sticky="ew", padx=20)

        self.barra = ctk.CTkProgressBar(cartao, height=8, corner_radius=4, progress_color=VERMELHO)
        self.barra.set(0)
        self.barra.grid(row=10, column=0, sticky="ew", padx=20, pady=(16, 0))

        rodape = ctk.CTkFrame(cartao, fg_color="transparent")
        rodape.grid(row=11, column=0, sticky="ew", padx=20, pady=(8, 18))
        rodape.grid_columnconfigure(0, weight=1)
        self.status = ctk.CTkLabel(
            rodape, text="Cole o link de um vídeo do YouTube.", font=self.fonte_pequena,
            text_color=TEXTO_SUAVE, anchor="w", justify="left",
        )
        self.status.grid(row=0, column=0, sticky="ew")
        self.botao_abrir = ctk.CTkButton(
            rodape, text="Abrir pasta", command=self._abrir_pasta, width=110, height=30,
            corner_radius=8, fg_color="transparent", border_width=1, border_color=BORDA,
            text_color=TEXTO, hover_color=BORDA, font=self.fonte_pequena,
        )
        # Quebra o status em várias linhas quando a janela fica estreita
        rodape.bind("<Configure>", lambda e: self.status.configure(wraplength=max(e.width - 130, 150)))
        self.faixa.bind(
            "<Configure>", lambda e: self.texto_faixa.configure(wraplength=max(e.width - 170, 150))
        )

        self.controles = [
            self.campo_link, self.botao_colar, self.campo_nome, *self.botoes_formato.values(),
            self.campo_pasta, self.botao_pasta, self.botao_baixar,
        ]
        self.after(50, self.campo_link.focus_set)

    def _rotulo(self, pai, texto: str, linha: int) -> None:
        ctk.CTkLabel(pai, text=texto, font=self.fonte_rotulo, anchor="w").grid(
            row=linha, column=0, sticky="ew", padx=20, pady=(18 if linha == 0 else 14, 6)
        )

    def _entrada(self, pai, dica: str, **kwargs) -> ctk.CTkEntry:
        return ctk.CTkEntry(
            pai, placeholder_text=dica or None, height=40, corner_radius=10,
            border_width=1, border_color=BORDA, font=self.fonte, **kwargs,
        )

    def _botao_secundario(self, pai, texto: str, comando) -> ctk.CTkButton:
        return ctk.CTkButton(
            pai, text=texto, command=comando, width=92, height=40, corner_radius=10,
            fg_color=BORDA, hover_color=("#d3d5db", "#3a3a40"),
            text_color=TEXTO, font=self.fonte_rotulo,
        )

    def _atualizar_rotulo_versao(self) -> None:
        motor, _ = atualizador.motor_em_uso()
        self.rotulo_versao.configure(text=f"v{__version__}\nyt-dlp {motor}")

    # ---------- ações ----------

    def _colar(self) -> None:
        try:
            texto = self.clipboard_get().strip()
        except tk.TclError:
            return
        self.campo_link.delete(0, "end")
        self.campo_link.insert(0, texto)

    def _escolher_formato(self, valor: str) -> None:
        self.formato.set(valor)
        for chave, botao in self.botoes_formato.items():
            if chave == valor:
                botao.configure(fg_color=VERMELHO, hover_color=VERMELHO_HOVER, text_color="white")
            else:
                botao.configure(fg_color=BORDA, hover_color=("#d3d5db", "#3a3a40"), text_color=TEXTO)
        # A qualidade máxima só muda algo no vídeo; no MP3 a chave fica desativada.
        self.chave_maxima.configure(state="normal" if valor == "MP4" else "disabled")

    def _escolher_pasta(self) -> None:
        pasta = filedialog.askdirectory(initialdir=self.pasta.get() or None)
        if pasta:
            self.pasta.set(pasta)

    def _abrir_pasta(self) -> None:
        if self.ultimo_arquivo and self.ultimo_arquivo.exists():
            os.startfile(self.ultimo_arquivo.parent)

    def _habilitar(self, ativo: bool) -> None:
        estado = "normal" if ativo else "disabled"
        for controle in self.controles:
            controle.configure(state=estado)
        self.chave_maxima.configure(state="disabled")
        if ativo:
            self._escolher_formato(self.formato.get())
        self.botao_baixar.configure(text="Baixar" if ativo else "Baixando…")

    def _mostrar_status(self, texto: str, cor=TEXTO_SUAVE) -> None:
        self.status.configure(text=texto, text_color=cor)

    def _iniciar(self) -> None:
        if self.baixando or self.botao_baixar.cget("state") == "disabled":
            return
        link = self.campo_link.get().strip()
        if not link:
            self._mostrar_status("Cole o link do vídeo primeiro.", VERMELHO)
            self.campo_link.focus_set()
            return
        formato = self.formato.get().lower()
        pasta = Path(self.pasta.get().strip() or Path.home() / "Downloads")
        qualidade = "maxima" if self.maxima.get() else "compativel"

        salvar_config({"pasta": str(pasta), "formato": formato, "qualidade": qualidade})
        self.botao_abrir.grid_remove()
        self._barra_parada(0)
        self._mostrar_status("Iniciando…")
        self._habilitar(False)
        self.baixando = True

        threading.Thread(
            target=self._trabalhar,
            args=(link, formato, pasta, self.campo_nome.get(), qualidade),
            daemon=True,
        ).start()

    def _trabalhar(self, link: str, formato: str, pasta: Path, nome: str, qualidade: str) -> None:
        """Roda fora da thread do Tk: só conversa com a interface pela fila."""
        try:
            arquivo = atualizador.baixar_com_recuperacao(
                link, formato, pasta, nome, self.eventos.put, qualidade,
                ao_verificar=lambda: self.eventos.put({"etapa": "verificando"}),
                ao_trocar_motor=lambda: self.eventos.put({"etapa": "motor_trocado"}),
            )
            self.eventos.put({"etapa": "concluido", "arquivo": arquivo})
        except ErroDownload as erro:
            self.eventos.put({"etapa": "erro", "mensagem": str(erro)})
        except Exception as erro:  # noqa: BLE001 - qualquer falha precisa voltar à tela
            log.exception("Erro inesperado")
            self.eventos.put({"etapa": "erro", "mensagem": f"Erro inesperado: {erro}"})

    # ---------- atualizações ----------

    def _verificar_atualizacoes(self) -> None:
        """Thread de fundo: falhas de rede aqui nunca atrapalham o uso do app."""
        try:
            nova = atualizador.verificar_app()
            if nova:
                self.eventos.put({"etapa": "app_nova", "nova": nova})
        except Exception:  # noqa: BLE001
            log.warning("Não foi possível verificar atualização do app", exc_info=True)
        try:
            if atualizador.atualizar_motor():
                self.eventos.put({"etapa": "motor_novo"})
        except Exception:  # noqa: BLE001
            log.warning("Não foi possível atualizar o motor", exc_info=True)

    def _instalar_atualizacao(self) -> None:
        if self.baixando or not self.nova_versao:
            return
        self.botao_atualizar.configure(state="disabled")
        self._habilitar(False)
        self.texto_faixa.configure(text="Baixando atualização…")
        nova = self.nova_versao

        def tarefa():
            try:
                atualizador.instalar_app(
                    nova, lambda p: self.eventos.put({"etapa": "app_progresso", "fracao": p})
                )
                self.eventos.put({"etapa": "app_instalando"})
            except Exception as erro:  # noqa: BLE001
                log.exception("Falha ao instalar atualização")
                self.eventos.put({"etapa": "app_falhou", "mensagem": str(erro)})

        threading.Thread(target=tarefa, daemon=True).start()

    def _aplicar_motor_novo(self) -> None:
        atualizador.recarregar_motor()
        self._precarregar()
        self._atualizar_rotulo_versao()

    # ---------- eventos ----------

    def _barra_parada(self, valor: float) -> None:
        self.barra.stop()
        self.barra.configure(mode="determinate")
        self.barra.set(valor)

    def _barra_animada(self) -> None:
        if self.barra.cget("mode") != "indeterminate":
            self.barra.configure(mode="indeterminate")
            self.barra.start()

    def _processar_eventos(self) -> None:
        while not self.eventos.empty():
            self._tratar_evento(self.eventos.get_nowait())
        self.after(100, self._processar_eventos)

    def _tratar_evento(self, evento: dict) -> None:
        etapa = evento["etapa"]
        if etapa == "baixando":
            porcentagem = evento["porcentagem"]
            if porcentagem is None:
                self._barra_animada()
                self._mostrar_status(f"Baixando…   {evento['velocidade']}")
            else:
                self._barra_parada(porcentagem / 100)
                self._mostrar_status(
                    f"Baixando {porcentagem:.0f}%   ·   {evento['velocidade']}   ·   faltam {evento['eta']}"
                )
        elif etapa == "convertendo":
            self._barra_animada()
            self._mostrar_status("Convertendo…")
        elif etapa == "verificando":
            self._barra_animada()
            self._mostrar_status("Falhou — verificando o motor de download…")
        elif etapa == "motor_trocado":
            self._atualizar_rotulo_versao()
            self._mostrar_status("Motor revertido para a versão anterior. Tentando de novo…")
        elif etapa == "concluido":
            self.ultimo_arquivo = evento["arquivo"]
            self._barra_parada(1)
            self._mostrar_status(f"✓  {self.ultimo_arquivo.name}", VERDE)
            self.botao_abrir.grid(row=0, column=1, sticky="e", padx=(8, 0))
            self.campo_link.delete(0, "end")
            self.campo_nome.delete(0, "end")
            self._fim_download()
        elif etapa == "erro":
            self._barra_parada(0)
            self._mostrar_status(f"Não foi possível baixar: {evento['mensagem']}", VERMELHO)
            self._fim_download()
        elif etapa == "app_nova":
            self.nova_versao = evento["nova"]
            self.texto_faixa.configure(text=f"Nova versão {self.nova_versao.versao} disponível.")
            self.faixa.grid(row=1, column=0, sticky="ew", padx=24, pady=(0, 12))
        elif etapa == "app_progresso":
            self.texto_faixa.configure(text=f"Baixando atualização… {evento['fracao'] * 100:.0f}%")
        elif etapa == "app_instalando":
            self.texto_faixa.configure(text="Instalando… o baixa vai reabrir sozinho.")
            self.after(800, self.destroy)
        elif etapa == "app_falhou":
            self.texto_faixa.configure(text=f"Não foi possível atualizar: {evento['mensagem']}")
            self.botao_atualizar.configure(state="normal")
            self._habilitar(True)
        elif etapa == "motor_novo":
            if self.baixando:
                self.recarregar_motor_pendente = True
            else:
                self._aplicar_motor_novo()

    def _fim_download(self) -> None:
        self.baixando = False
        self._habilitar(True)
        self.focus_set()  # devolve os placeholders aos campos vazios
        if self.recarregar_motor_pendente:
            self.recarregar_motor_pendente = False
            self._aplicar_motor_novo()


def configurar_log() -> None:
    PASTA_DADOS.mkdir(parents=True, exist_ok=True)
    manipulador = logging.handlers.RotatingFileHandler(
        ARQUIVO_LOG, maxBytes=1_000_000, backupCount=2, encoding="utf-8"
    )
    manipulador.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    raiz = logging.getLogger()
    raiz.addHandler(manipulador)
    raiz.setLevel(logging.INFO)
    logging.getLogger("baixa").setLevel(logging.INFO)
    logging.getLogger("baixa.nucleo").setLevel(logging.WARNING)


def main() -> None:
    configurar_log()
    atualizador.ativar_motor()
    ctk.set_appearance_mode("system")
    App().mainloop()


if __name__ == "__main__":
    main()
