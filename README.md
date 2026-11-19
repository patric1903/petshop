# PetCare – Sistema de Gestão para Petshop e Clínica Veterinária

Projeto Tecnológico em Desenvolvimento de Sistemas – ADS / ULBRA EAD.
Aluno: Patric Fagundes Hennig

Sistema web para pequenos petshops/clínicas: cadastro de clientes e pets, agenda de
banho, tosa e consulta **com verificação de conflito por profissional**, histórico de
vacinas com **alerta de próxima dose**, financeiro simplificado e três perfis de acesso.

## Tecnologias e versões
| Item | Versão |
|---|---|
| Python | 3.12 ou superior |
| Django | 5.2 |
| PostgreSQL | 16 (SQLite apenas como alternativa local) |
| Bootstrap | 5.3 (CDN) |
| Servidor | Gunicorn 27 + WhiteNoise 6 (arquivos estáticos) |
| Hospedagem | Render (aplicação e PostgreSQL) |

## Funcionalidades (casos de uso)
UC01 Login · UC02 CRUD de clientes · UC03 CRUD de pets · UC04 Agendar · UC05 Agenda ·
UC06 Cancelar/Reagendar · UC07 Registrar atendimento · UC08 Registrar vacina ·
UC09 Histórico do pet · UC10 Conflito de horário · UC11 Alerta de vacina ·
UC12 Receita · UC13 Relatório financeiro · UC14 Funcionários (e cadastro de serviços).

## Perfis de acesso
| Perfil | Pode |
|---|---|
| **Atendente** | clientes, pets, agendar/reagendar/cancelar, agenda completa, vacinas, histórico |
| **Profissional** | **apenas** a própria agenda, concluir os próprios atendimentos, vacinas e histórico. **Não herda** as permissões do Atendente |
| **Administrador** | tudo, mais receitas, relatório financeiro, funcionários e serviços |

## Regras de negócio principais
- `hora_fim = início + duração do serviço`; dois atendimentos do mesmo profissional não podem se sobrepor (horários colados são permitidos; cancelados liberam o horário).
- `valor_cobrado` é gravado no agendamento no momento da reserva: reajustar o serviço não altera atendimentos antigos.
- Só é possível cancelar/reagendar atendimentos ainda **não iniciados**. O profissional conclui atendimentos do **dia atual** (ou de dias anteriores); atendimentos de dias futuros não podem ser concluídos.
- Vacina registra quem aplicou e a data da próxima dose; o painel destaca vencidas e a vencer em 30 dias.
- Funcionários não são excluídos, apenas desativados (campo `ativo`, que bloqueia o login).
- Pagamento integral: um atendimento concluído gera uma única receita (pagamento parcial fora do escopo).
- Senhas gravadas somente como hash PBKDF2; sessão expira em 8 h ou ao fechar o navegador; HTTPS obrigatório em produção.

## Instalação e execução local
```bash
git clone https://github.com/patric1903/petshop && cd petshop
python -m venv venv && source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt

# PostgreSQL (opcional; sem isso usa SQLite)
createdb petcare
cp .env.example .env     # ajuste DATABASE_URL e exporte as variáveis (ou use export direto)
export DATABASE_URL=postgres://USUARIO:SENHA@localhost:5432/petcare

python manage.py migrate        # cria as tabelas (equivale ao schema.sql)
python manage.py seed           # cria usuários e dados de demonstração
python manage.py runserver      # http://127.0.0.1:8000
```
Testes automatizados: `python manage.py test` (26 testes).

## Usuários de demonstração
| Perfil | E-mail | Senha |
|---|---|---|
| Administrador | admin@petcare.com | Admin@12345 |
| Atendente | atendente@petcare.com | Atend@12345 |
| Profissional | bia@petcare.com | Prof@12345 |
| Profissional | vet@petcare.com | Prof@12345 |

(Credenciais apenas de demonstração, geradas pelo comando `seed`.)

## Banco de dados
`schema.sql` contém a estrutura PostgreSQL gerada a partir das migrações
(`python manage.py sqlmigrate core 0001`). Os dados iniciais vêm de `python manage.py seed`.

## Orientações para análise do código
- `core/models.py`: entidades e regras (conflito de horário, valor congelado, alerta de vacina).
- `core/permissions.py`: controle de acesso por perfil.
- `core/views.py`: casos de uso; `core/forms.py`: validações; `core/templates/`: telas.
- `core/tests.py`: testes das regras e das permissões.
- `config/settings.py`: configuração (banco por `DATABASE_URL`, segurança, sessão).

## Publicação (Render)
1. Envie o código para o GitHub (repositório público).
2. No Render: *New → Blueprint*, selecione o repositório (usa `render.yaml`).
3. O build executa `build.sh` (dependências, estáticos, migrações e dados de demonstração).
