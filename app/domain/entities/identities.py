import re
from app.domain.errors import DomainError

def validar_cpf(cpf: str) -> str | None:
    cpf = re.sub(r"\D", "", cpf)

    if len(cpf) != 11:
        return None

    if cpf == cpf[0] * 11:
        return None

    # Primeiro dígito
    soma = sum(int(cpf[i]) * (10 - i) for i in range(9))
    resto = (soma * 10) % 11
    digito1 = 0 if resto == 10 else resto

    if digito1 != int(cpf[9]):
        return None

    # Segundo dígito
    soma = sum(int(cpf[i]) * (11 - i) for i in range(10))
    resto = (soma * 10) % 11
    digito2 = 0 if resto == 10 else resto

    if digito2 != int(cpf[10]):
        return None

    return cpf

def validar_cnpj(cnpj: str) -> str | None:
    cnpj = re.sub(r"\D", "", cnpj)

    if len(cnpj) != 14:
        return None

    if cnpj == cnpj[0] * 14:
        return None

    pesos1 = [5,4,3,2,9,8,7,6,5,4,3,2]
    soma = sum(int(cnpj[i]) * pesos1[i] for i in range(12))
    resto = soma % 11
    digito1 = 0 if resto < 2 else 11 - resto

    if digito1 != int(cnpj[12]):
        return None

    pesos2 = [6] + pesos1
    soma = sum(int(cnpj[i]) * pesos2[i] for i in range(13))
    resto = soma % 11
    digito2 = 0 if resto < 2 else 11 - resto

    if digito2 != int(cnpj[13]):
        return None

    return cnpj

class CPF:
    def __init__(self, value: str):
        cpf = validar_cpf(value)
        if not cpf:
            raise DomainError("CPF inválido")
        self.value = cpf

class CNPJ:
    def __init__(self, value: str):
        cnpj = validar_cnpj(value)
        if not cnpj:
            raise DomainError("CNPJ inválido")
        self.value = cnpj