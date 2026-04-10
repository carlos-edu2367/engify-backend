"""
Adapter: Mailgun Email (Engify)

Implementa EmailPort usando a API do Mailgun.

Segurança:
- API key via variável de ambiente
- Validação básica de email antes de enviar
- Timeout para evitar travamentos
- Nunca loga corpos de email (podem conter tokens sensíveis)
"""
import logging
import re
from typing import Optional

import httpx

from app.application.ports.email_port import (
    EmailPort,
    RecoveryCodeEmailInput,
    ConviteEmailInput,
)

logger = logging.getLogger(__name__)

_EMAIL_REGEX = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
_MAILGUN_API_URL = "https://api.mailgun.net/v3"
_TIMEOUT_SEGUNDOS = 15.0


class MailgunEmailAdapter(EmailPort):
    """Adapter de email transacional usando Mailgun REST API."""

    def __init__(self, api_key: str, domain: str, remetente: str, frontend_url: str) -> None:
        if not api_key:
            raise ValueError("MAILGUN_API_KEY é obrigatório.")
        if not domain:
            raise ValueError("MAILGUN_DOMAIN é obrigatório.")
        if not remetente:
            raise ValueError("MAILGUN_FROM é obrigatório.")

        self._domain = domain
        self._remetente = remetente
        self._frontend_url = frontend_url.rstrip("/")
        self._client = httpx.AsyncClient(
            auth=("api", api_key),
            timeout=_TIMEOUT_SEGUNDOS,
        )

    async def enviar_recovery_code(self, input: RecoveryCodeEmailInput) -> None:
        """Envia email com link assinado de recuperação de senha."""
        if not self._validar_email(input.destinatario):
            logger.warning("Recovery code email: destinatário inválido")
            return

        reset_link = (
            f"{self._frontend_url}/recovery"
            f"?uid={input.user_id}"
            f"&token={input.code}"
        )

        conteudo = f"""
            <p>Olá, <strong>{input.nome}</strong>!</p>
            <p>Recebemos uma solicitação de recuperação de senha para a sua conta Engify.</p>
            <p>Clique no botão abaixo para definir uma nova senha.
               O link é válido por <strong>30 minutos</strong> e pode ser usado apenas uma vez.</p>
            <p style="font-size: 13px; color: #6b7280;">
                Se você não solicitou esta recuperação, ignore este e-mail com segurança.
                Sua senha permanece inalterada.
            </p>
        """
        corpo_html = self._gerar_layout_base(
            titulo_pagina="Recuperação de Senha",
            conteudo_html=conteudo,
            cta_link=reset_link,
            cta_texto="Redefinir Senha",
        )
        await self._enviar(
            para=input.destinatario,
            assunto="Recuperação de senha — Engify",
            corpo_html=corpo_html,
        )

    async def enviar_convite(self, input: ConviteEmailInput) -> None:
        """Envia email de convite para novo usuário ingressar no time."""
        if not self._validar_email(input.destinatario):
            logger.warning("Convite email: destinatário inválido")
            return

        link_registro = f"{self._frontend_url}/register?invite={input.solicitacao_id}"

        conteudo = f"""
            <p>Olá!</p>
            <p>Você foi convidado para fazer parte do time <strong>{input.team_name}</strong> na plataforma Engify.</p>
            <p>Sua função no time será: <strong>{input.role}</strong>.</p>
            <p>Clique no botão abaixo para criar sua conta. O convite é válido por <strong>7 dias</strong>.</p>
            <p style="font-size: 13px; color: #6b7280;">
                Se você não esperava este convite, pode ignorar este e-mail com segurança.
            </p>
        """
        corpo_html = self._gerar_layout_base(
            titulo_pagina="Convite para o Engify",
            conteudo_html=conteudo,
            cta_link=link_registro,
            cta_texto="Criar Minha Conta",
        )
        await self._enviar(
            para=input.destinatario,
            assunto=f"Convite para o time {input.team_name} — Engify",
            corpo_html=corpo_html,
        )

    async def _enviar(self, para: str, assunto: str, corpo_html: str) -> None:
        dados = {
            "from": self._remetente,
            "to": para,
            "subject": assunto,
            "html": corpo_html,
        }
        try:
            response = await self._client.post(
                f"{_MAILGUN_API_URL}/{self._domain}/messages",
                data=dados,
            )
            if response.status_code in (200, 202):
                logger.info("Email enviado com sucesso (status=%d)", response.status_code)
            else:
                logger.error("Mailgun retornou erro (status=%d)", response.status_code)
        except httpx.TimeoutException:
            logger.error("Timeout ao enviar email via Mailgun")
        except Exception as exc:
            logger.error("Erro inesperado ao enviar email: %s", type(exc).__name__)

    def _gerar_layout_base(
        self,
        titulo_pagina: str,
        conteudo_html: str,
        cta_link: Optional[str] = None,
        cta_texto: Optional[str] = None,
    ) -> str:
        botao_html = ""
        if cta_link and cta_texto:
            botao_html = f"""
            <tr>
                <td align="center" style="padding: 20px 0 0 0;">
                    <table border="0" cellspacing="0" cellpadding="0">
                        <tr>
                            <td align="center" style="border-radius: 6px;" bgcolor="#2563eb">
                                <a href="{cta_link}" target="_blank"
                                   style="font-size: 16px; font-family: sans-serif; color: #ffffff;
                                          text-decoration: none; border-radius: 6px; padding: 12px 24px;
                                          border: 1px solid #2563eb; display: inline-block; font-weight: bold;">
                                    {cta_texto}
                                </a>
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>
            """

        return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{titulo_pagina}</title>
</head>
<body style="margin:0;padding:0;background-color:#f3f4f6;font-family:'Helvetica Neue',Helvetica,Arial,sans-serif;">
    <table border="0" cellpadding="0" cellspacing="0" width="100%">
        <tr>
            <td align="center" style="padding: 40px 0 30px 0;">
                <table border="0" cellpadding="0" cellspacing="0" width="600" style="border-collapse:collapse;">
                    <tr>
                        <td align="center" style="padding:0 0 20px 0;color:#2563eb;font-size:28px;font-weight:bold;letter-spacing:2px;">
                            ENGIFY
                        </td>
                    </tr>
                </table>
                <table border="0" cellpadding="0" cellspacing="0" width="600"
                       style="border-collapse:collapse;background-color:#ffffff;border-radius:12px;
                              box-shadow:0 4px 6px -1px rgba(0,0,0,0.1);">
                    <tr>
                        <td style="padding:40px 30px;">
                            <table border="0" cellpadding="0" cellspacing="0" width="100%">
                                <tr>
                                    <td style="color:#1f2937;font-size:24px;font-weight:bold;padding-bottom:20px;">
                                        {titulo_pagina}
                                    </td>
                                </tr>
                                <tr>
                                    <td style="color:#4b5563;font-size:16px;line-height:24px;padding-bottom:10px;">
                                        {conteudo_html}
                                    </td>
                                </tr>
                                {botao_html}
                            </table>
                        </td>
                    </tr>
                </table>
                <table border="0" cellpadding="0" cellspacing="0" width="600" style="border-collapse:collapse;">
                    <tr>
                        <td align="center" style="padding:30px 30px 10px 30px;color:#9ca3af;font-size:12px;">
                            <p style="margin:0;">&copy; 2026 Engify. Todos os direitos reservados.</p>
                            <p style="margin:0;margin-top:8px;">Plataforma de gestão de obras.</p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>"""

    async def fechar(self) -> None:
        await self._client.aclose()

    def _validar_email(self, email: str) -> bool:
        if not email or not isinstance(email, str):
            return False
        return bool(_EMAIL_REGEX.match(email.strip()))
