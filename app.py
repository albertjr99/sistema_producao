from flask import Flask, render_template, request, redirect, session, url_for, flash
from flask import session, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from flask_migrate import Migrate
import calendar

app = Flask(__name__)
app.secret_key = 'chave-secreta'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///producao.db'
db = SQLAlchemy(app)
migrate = Migrate(app, db)

class Usuario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    senha = db.Column(db.String(200), nullable=False)
    tipo = db.Column(db.String(20), nullable=False)
    modalidade = db.Column(db.String(20))
    primeiro_acesso_realizado = db.Column(db.Boolean, default=False)


class LinhaProducao(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    mes = db.Column(db.String(20), nullable=False)
    semana = db.Column(db.String(50), nullable=False)
    indice_linha = db.Column(db.Integer, nullable=False)
    numero_processo = db.Column(db.String(50))
    requerente = db.Column(db.String(100))
    fase = db.Column(db.String(50))
    observacao = db.Column(db.Text)
    data_registro = db.Column(db.DateTime, default=datetime.utcnow)
    averbacao = db.Column(db.Boolean, default=False)
    desaverbacao = db.Column(db.Boolean, default=False)
    conf_av_desav = db.Column(db.Boolean, default=False)
    ctc = db.Column(db.Boolean, default=False)
    conf_ctc = db.Column(db.Boolean, default=False)
    dtc = db.Column(db.Boolean, default=False)
    conf_dtc = db.Column(db.Boolean, default=False)
    in_68 = db.Column(db.Boolean, default=False)
    dpor = db.Column(db.Boolean, default=False)
    registro_atos = db.Column(db.Boolean, default=False)
    ag_completar = db.Column(db.Boolean, default=False)
    outros = db.Column(db.Boolean, default=False)

    usuario = db.relationship('Usuario', backref='linhas')

def gerar_semanas(mes, ano):
    semanas = []
    primeiro_dia = datetime(ano, mes, 1)
    ultimo_dia = datetime(ano, mes, calendar.monthrange(ano, mes)[1])
    semana = []
    dia = primeiro_dia
    while dia <= ultimo_dia:
        if dia.weekday() < 5:
            semana.append(dia.strftime('%d/%m'))
        if dia.weekday() == 4 or dia == ultimo_dia:
            if semana:
                semanas.append(f"{semana[0]} a {semana[-1]}")
                semana = []
        dia += timedelta(days=1)
    return semanas

# Resto do código será completado na próxima etapa

@app.route('/')
def index():
    return render_template('login.html')

from sqlalchemy import func

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template('login.html')

    nome = request.form['nome']
    senha = request.form['senha']
    
    # Busca ignorando diferenças de maiúsculas/minúsculas
    usuario = Usuario.query.filter(func.lower(Usuario.nome) == nome.lower()).first()

    if usuario and check_password_hash(usuario.senha, senha):
        session['usuario_id'] = usuario.id
        session['usuario_tipo'] = usuario.tipo
        if usuario.tipo == 'analista':
            return redirect(url_for('registrar_producao'))
        elif usuario.tipo == 'estagiaria':
            return redirect(url_for('painel_estagiarias'))
        else:
            return redirect(url_for('painel_gerente'))

    return 'Login inválido'


@app.route('/logout')
def logout():
    session.clear()  # ou session.pop('usuario', None)
    return redirect(url_for('login'))


@app.route('/primeiro-acesso', methods=['POST'])
def primeiro_acesso():
    email = request.form['email']
    nova_senha = request.form['nova_senha']
    usuario = Usuario.query.filter_by(email=email).first()
    if usuario:
        if usuario.primeiro_acesso_realizado:
            flash('A senha já foi definida anteriormente.')
        else:
            usuario.senha = generate_password_hash(nova_senha)
            usuario.primeiro_acesso_realizado = True
            db.session.commit()
            flash('Senha definida com sucesso. Agora você pode fazer login.')
    else:
        flash('Usuário não encontrado.')
    return redirect(url_for('index'))

@app.route('/acompanhamento-anual')
def acompanhamento_anual():
    campos = [
        'averbacao', 'desaverbacao', 'conf_av_desav', 'ctc',
        'conf_ctc', 'dtc', 'conf_dtc', 'in_68', 'dpor',
        'registro_atos', 'ag_completar', 'outros'
    ]
    meses = ['Junho', 'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro']

    # Inicializa estrutura para totais
    totais_anuais = {mes: {campo: 0 for campo in campos} for mes in meses}

    # Coleta e contabiliza dados
    producoes = LinhaProducao.query.filter(LinhaProducao.mes.in_(meses)).all()
    for producao in producoes:
        for campo in campos:
            if getattr(producao, campo, False):
                totais_anuais[producao.mes][campo] += 1

    # Prepara dados agregados para gráfico
    grafico_anos = {
        campo: sum(totais[campo] for totais in totais_anuais.values())
        for campo in campos
    }

    return render_template(
        'acompanhamento_anual.html',
        totais_anuais=totais_anuais,
        grafico_anos=grafico_anos,
        meses=meses,
        campos=campos
    )


@app.route('/painel-gerente', methods=['GET', 'POST'])
def painel_gerente():
    if 'usuario_id' not in session or session['usuario_tipo'] == 'analista':
        flash('Acesso não autorizado.')
        return redirect(url_for('index'))

    analistas_presencial = Usuario.query.filter_by(tipo='analista', modalidade='presencial').all()
    analistas_teletrabalho = Usuario.query.filter_by(tipo='analista', modalidade='teletrabalho').all()

    analista_id = request.args.get('analista_id') or request.form.get('analista_id')
    usuario_selecionado = Usuario.query.get(analista_id) if analista_id else None

    mes = request.args.get('mes') or request.form.get('mes') or 'Junho'
    ano = 2025
    meses = ['Junho', 'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro']
    mes_index = meses.index(mes)
    semanas = gerar_semanas(mes_index + 6, ano)
    linhas = 33 if usuario_selecionado and usuario_selecionado.modalidade == 'teletrabalho' else 28

    campos_checkbox = [
        'averbacao', 'desaverbacao', 'conf_av_desav', 'ctc',
        'conf_ctc', 'dtc', 'conf_dtc', 'in_68', 'dpor',
        'registro_atos', 'ag_completar', 'outros'
    ]

    processos_info = {}
    totais = {}
    total_feito = 0
    percentual_meta = 0
    meta = 100
    alertas = {}

    if usuario_selecionado:
        meta = 112 if usuario_selecionado.modalidade == "teletrabalho" else 100

        if request.method == 'POST':
            for semana in semanas:
                for i in range(linhas):
                    producao = LinhaProducao.query.filter_by(
                        usuario_id=usuario_selecionado.id,
                        mes=mes,
                        semana=semana
                    ).offset(i).first()

                    if not producao:
                        producao = LinhaProducao(
                            usuario_id=usuario_selecionado.id,
                            mes=mes,
                            semana=semana,
                            indice_linha=i,
                            data_registro=datetime.utcnow()
                        )
                        db.session.add(producao)

                    producao.numero_processo = request.form.get(f'{semana}_{i}_numero_processo') or ""
                    producao.requerente = request.form.get(f'{semana}_{i}_requerente') or ""
                    producao.fase = request.form.get(f'{semana}_{i}_fase') or ""

                    for campo in campos_checkbox:
                        producao_valor = request.form.get(f'{semana}_{i}_{campo}')
                        setattr(producao, campo, producao_valor is not None)

                    producao.observacao = request.form.get(f'{semana}_{i}_obs') or ""

            db.session.commit()
            flash("Produção atualizada com sucesso.")
            return redirect(url_for('painel_gerente', analista_id=usuario_selecionado.id, mes=mes))

        processos_info = {
            semana: [
                LinhaProducao.query.filter_by(usuario_id=usuario_selecionado.id, semana=semana, mes=mes)
                .offset(i).first()
                for i in range(linhas)
            ]
            for semana in semanas
        }

        totais = {semana: {campo: 0 for campo in campos_checkbox} for semana in semanas}
        for semana in semanas:
            producoes = LinhaProducao.query.filter_by(usuario_id=usuario_selecionado.id, semana=semana, mes=mes).all()
            for producao in producoes:
                for campo in campos_checkbox:
                    if getattr(producao, campo):
                        totais[semana][campo] += 1

        total_feito = sum(sum(t.values()) for t in totais.values())
        percentual_meta = min(int((total_feito / meta) * 100), 100)

        for semana in semanas:
            total_atividades = sum(totais[semana].values())
            esperado = 25 if usuario_selecionado.modalidade == 'presencial' else 28
            if total_atividades < esperado:
                alertas[semana] = f"Faltam {esperado - total_atividades} tarefas"

    totais_anuais = {mes: {campo: 0 for campo in campos_checkbox} for mes in meses}
    for mes_ref in meses:
        producoes = LinhaProducao.query.filter_by(mes=mes_ref).all()
        for producao in producoes:
            for campo in campos_checkbox:
                if getattr(producao, campo):
                    totais_anuais[mes_ref][campo] += 1

    return render_template(
        'painel_gerente.html',
        analistas_presencial=analistas_presencial,
        analistas_teletrabalho=analistas_teletrabalho,
        usuario_selecionado=usuario_selecionado,
        semanas=semanas,
        processos_info=processos_info,
        linhas=linhas,
        totais=totais,
        total_feito=total_feito,
        percentual_meta=percentual_meta,
        meta=meta,
        mes=mes,
        totais_anuais=totais_anuais,
        alertas=alertas
    )
@app.route('/acompanhamento-pessoal')
@login_required
def acompanhamento_pessoal():
    usuario = current_user
    mes = datetime.now().strftime('%B').capitalize()

    semanas = obter_semanas_do_mes(mes)
    campos = ['averbacao', 'desaverbacao', 'conf_av_desav', 'ctc', 'conf_ctc', 'dtc',
              'conf_dtc', 'in_68', 'dpor', 'registro_atos', 'ag_completar', 'outros']

    totais = {}
    total_feito = 0
    for semana in semanas:
        contagem = {campo: 0 for campo in campos}
        processos = Processo.query.filter_by(usuario_id=usuario.id, semana=semana, mes=mes).all()
        for processo in processos:
            for campo in campos:
                if getattr(processo, campo):
                    contagem[campo] += 1
                    total_feito += 1
        totais[semana] = contagem

    meta = 100  # Adapte conforme necessário
    percentual_meta = round((total_feito / meta) * 100, 1) if meta > 0 else 0

    return render_template(
        'acompanhamento_pessoal.html',
        usuario=usuario,
        semanas=semanas,
        totais=totais,
        campos=campos,
        total_feito=total_feito,
        meta=meta,
        percentual_meta=percentual_meta,
        mes=mes
    )



@app.route('/editar-producao/<int:id>', methods=['GET', 'POST'])
def editar_producao(id):
    producao = LinhaProducao.query.get_or_404(id)
    if request.method == 'POST':
        producao.numero_processo = request.form['numero_processo']
        producao.requerente = request.form['requerente']
        producao.fase = request.form['fase']
        db.session.commit()
        return redirect(url_for('painel_gerente'))
    return render_template('editar_producao.html', producao=producao)

# Continuação será feita na próxima etapa

@app.route('/registrar-producao', methods=['GET', 'POST'])
def registrar_producao():
    if 'usuario_id' not in session or session['usuario_tipo'] != 'analista':
        flash('Acesso não autorizado.')
        return redirect(url_for('index'))

    usuario = Usuario.query.get(session['usuario_id'])
    meses = ['Junho', 'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro']
    ano = 2025

    mes_param = request.args.get('mes') or 'Junho'
    mes_atual = mes_param if mes_param in meses else 'Junho'
    mes_index = meses.index(mes_atual)
    mes_anterior = meses[mes_index - 1] if mes_index > 0 else meses[-1]
    mes_posterior = meses[mes_index + 1] if mes_index < len(meses) - 1 else meses[0]
    mes_num = mes_index + 6

    semanas = gerar_semanas(mes_num, ano)
    linhas = 33 if usuario.modalidade == 'teletrabalho' else 28
    campos = [
        'averbacao', 'desaverbacao', 'conf_av_desav', 'ctc',
        'conf_ctc', 'dtc', 'conf_dtc', 'in_68', 'dpor',
        'registro_atos', 'ag_completar', 'outros'
    ]

    if request.method == 'POST':
        for semana in semanas:
            for i in range(linhas):
                indice_linha = i + 1  # <<< ADICIONADO

                producao = LinhaProducao.query.filter_by(
                    usuario_id=usuario.id,
                    mes=mes_atual,
                    semana=semana,
                    indice_linha=indice_linha  # <<< ADICIONADO
                ).first()

                if not producao:
                    producao = LinhaProducao(
                        usuario_id=usuario.id,
                        mes=mes_atual,
                        semana=semana,
                        indice_linha=indice_linha,  # <<< ADICIONADO
                        data_registro=datetime.utcnow()
                    )
                    db.session.add(producao)

                for campo in campos:
                    producao_valor = request.form.get(f'{semana}_{i}_{campo}')
                    setattr(producao, campo, producao_valor is not None)

                producao.observacao = request.form.get(f'{semana}_{i}_obs') or ""

        db.session.commit()
        flash('Produção salva com sucesso!')
        return redirect(url_for('registrar_producao', mes=mes_atual))

    processos_info = {
        semana: [
            LinhaProducao.query.filter_by(usuario_id=usuario.id, mes=mes_atual, semana=semana, indice_linha=i + 1).first()
            for i in range(linhas)
        ]
        for semana in semanas
    }

    totais = {semana: {campo: 0 for campo in campos} for semana in semanas}
    for semana in semanas:
        producoes = LinhaProducao.query.filter_by(usuario_id=usuario.id, semana=semana, mes=mes_atual).all()
        for producao in producoes:
            for campo in campos:
                if getattr(producao, campo):
                    totais[semana][campo] += 1

    total_feito = sum(sum(t.values()) for t in totais.values())
    meta = 112 if usuario.modalidade == 'teletrabalho' else 100
    percentual_meta = min(int((total_feito / meta) * 100), 100)

    return render_template(
        'registrar_producao.html',
        usuario=usuario,
        semanas=semanas,
        linhas=linhas,
        campos=campos,
        processos_info=processos_info,
        totais=totais,
        total_feito=total_feito,
        percentual_meta=percentual_meta,
        meta=meta,
        mes_atual=mes_atual,
        mes_anterior=mes_anterior,
        mes_posterior=mes_posterior
    )

@app.template_filter('get_attr')
def get_attr(obj, name):
    return getattr(obj, name, None)


@app.route('/painel-estagiarias', methods=['GET', 'POST'])
def painel_estagiarias():
    if 'usuario_id' not in session or session['usuario_tipo'] != 'estagiaria':
        flash('Acesso não autorizado.')
        return redirect(url_for('index'))

    analistas_presencial = Usuario.query.filter_by(tipo='analista', modalidade='presencial').all()
    analistas_teletrabalho = Usuario.query.filter_by(tipo='analista', modalidade='teletrabalho').all()

    analista_id = request.args.get('analista_id') or request.form.get('analista_id')
    usuario_selecionado = Usuario.query.get(analista_id) if analista_id else None

    mes = request.args.get('mes') or request.form.get('mes') or 'Junho'
    ano = 2025
    meses = ['Junho', 'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro']
    mes_index = meses.index(mes)
    semanas = gerar_semanas(mes_index + 6, ano)
    linhas = 33 if usuario_selecionado and usuario_selecionado.modalidade == 'teletrabalho' else 28

    campos = ['numero_processo', 'requerente', 'fase']
    campos_checkbox = [
        'averbacao', 'desaverbacao', 'conf_av_desav', 'ctc',
        'conf_ctc', 'dtc', 'conf_dtc', 'in_68', 'dpor',
        'registro_atos', 'ag_completar', 'outros'
    ]

    if request.method == 'POST' and usuario_selecionado:
        for semana in semanas:
            for i in range(linhas):
                producao = LinhaProducao.query.filter_by(usuario_id=usuario_selecionado.id, semana=semana, mes=mes).offset(i).first()
                if not producao:
                    producao = LinhaProducao(
                        usuario_id=usuario_selecionado.id,
                        mes=mes,
                        semana=semana,
                        data_registro=datetime.utcnow()
                    )
                    db.session.add(producao)

                producao.numero_processo = request.form.get(f'{semana}_{i}_numero_processo') or ""
                producao.requerente = request.form.get(f'{semana}_{i}_requerente') or ""
                producao.fase = request.form.get(f'{semana}_{i}_fase') or ""
                producao.observacao = request.form.get(f'{semana}_{i}_obs') or ""

                for campo in campos_checkbox:
                    producao_valor = request.form.get(f'{semana}_{i}_{campo}')
                    setattr(producao, campo, producao_valor is not None)

        db.session.commit()
        flash('Edições salvas com sucesso!')

    processos_info = {}
    if usuario_selecionado:
        processos_info = {
            semana: [
                LinhaProducao.query.filter_by(usuario_id=usuario_selecionado.id, semana=semana, mes=mes).offset(i).first()
                for i in range(linhas)
            ]
            for semana in semanas
        }

    return render_template(
        'painel_estagiarias.html',
        analistas_presencial=analistas_presencial,
        analistas_teletrabalho=analistas_teletrabalho,
        processos_info=processos_info,
        semanas=semanas,
        linhas=linhas,
        campos=campos,
        usuario_selecionado=usuario_selecionado,
        mes=mes
    )

@app.route('/relatorio-geral')
def relatorio_geral():
    if 'usuario_id' not in session or session['usuario_tipo'] == 'analista':
        flash('Acesso não autorizado.')
        return redirect(url_for('index'))

    ano = 2025
    meses = ['Junho', 'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro']
    campos = [
        'averbacao', 'desaverbacao', 'conf_av_desav', 'ctc',
        'conf_ctc', 'dtc', 'conf_dtc', 'in_68', 'dpor',
        'registro_atos', 'ag_completar', 'outros'
    ]

    totais_gerais = {mes: {campo: 0 for campo in campos} for mes in meses}

    for mes in meses:
        producoes = LinhaProducao.query.filter_by(mes=mes).all()
        for producao in producoes:
            for campo in campos:
                if getattr(producao, campo):
                    totais_gerais[mes][campo] += 1

    return render_template(
        'relatorio_geral.html',
        totais_gerais=totais_gerais,
        campos=campos,
        meses=meses
    )


@app.route('/editar-producao-lote/<int:analista_id>', methods=['POST'])
def editar_producao_lote(analista_id):
    if 'usuario_id' not in session or session['usuario_tipo'] != 'estagiaria':
        flash('Acesso não autorizado.')
        return redirect(url_for('index'))

    usuario = Usuario.query.get_or_404(analista_id)
    mes = request.args.get('mes') or 'Junho'
    ano = 2025
    meses = ['Junho', 'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro']
    mes_index = meses.index(mes)
    semanas = gerar_semanas(mes_index + 6, ano)
    linhas = 33 if usuario.modalidade == 'teletrabalho' else 28

    for semana in semanas:
        for i in range(linhas):
            processo = LinhaProducao.query.filter_by(
                usuario_id=analista_id, semana=semana, mes=mes
            ).offset(i).first()

            if not processo:
                processo = LinhaProducao(
                    usuario_id=analista_id,
                    mes=mes,
                    semana=semana,
                    data_registro=datetime.utcnow()
                )
                db.session.add(processo)

            processo.numero_processo = request.form.get(f'{semana}_{i}_numero_processo') or ""
            processo.requerente = request.form.get(f'{semana}_{i}_requerente') or ""
            processo.fase = request.form.get(f'{semana}_{i}_fase') or ""

    db.session.commit()
    flash('Edições salvas com sucesso.')
    return redirect(url_for('painel_estagiarias', analista_id=analista_id, mes=mes))

if __name__ == '__main__':
    app.run(debug=True)
    











    









