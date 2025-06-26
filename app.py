from flask import Flask, render_template, request, redirect, session, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import LoginManager, login_user, logout_user, login_required, current_user, UserMixin
from sqlalchemy import func
from datetime import datetime, timedelta
import calendar

app = Flask(__name__)
app.secret_key = 'chave-secreta'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///producao.db'

# --- Banco de dados ---
db = SQLAlchemy(app)
migrate = Migrate(app, db)

# --- LoginManager ---
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# --- Models ---
class Usuario(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    senha = db.Column(db.String(200), nullable=False)
    tipo = db.Column(db.String(20), nullable=False)            # 'analista', 'estagiaria' ou 'gerente'
    modalidade = db.Column(db.String(20), nullable=True)        # 'presencial' ou 'teletrabalho'
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
    # checkboxes:
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

# --- Helpers ---
def gerar_semanas(mes: int, ano: int):
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

# --- Flask-Login user loader ---
@login_manager.user_loader
def load_user(user_id):
    return Usuario.query.get(int(user_id))

# --- Rotas públicas ---
@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template('login.html')

    nome = request.form['nome']
    senha = request.form['senha']
    usuario = Usuario.query.filter(func.lower(Usuario.nome) == nome.lower()).first()

    if usuario and check_password_hash(usuario.senha, senha):
        login_user(usuario)
        if usuario.tipo == 'analista':
            return redirect(url_for('registrar_producao'))
        elif usuario.tipo == 'estagiaria':
            return redirect(url_for('painel_estagiarias'))
        else:
            return redirect(url_for('painel_gerente'))
    flash('Login inválido.')
    return redirect(url_for('login'))

@app.route('/logout')
def logout():
    logout_user()
    session.clear()
    return redirect(url_for('login'))

@app.route('/primeiro-acesso', methods=['POST'])
def primeiro_acesso():
    email = request.form['email']
    nova_senha = request.form['nova_senha']
    user = Usuario.query.filter_by(email=email).first()
    if user:
        if user.primeiro_acesso_realizado:
            flash('Senha já definida.')
        else:
            user.senha = generate_password_hash(nova_senha)
            user.primeiro_acesso_realizado = True
            db.session.commit()
            flash('Senha definida. Faça login agora.')
    else:
        flash('Usuário não encontrado.')
    return redirect(url_for('login'))

# --- Acompanhamento anual (gerentes) ---
@app.route('/acompanhamento-anual')
@login_required
def acompanhamento_anual():
    if current_user.tipo != 'gerente':
        flash('Acesso negado.')
        return redirect(url_for('login'))
    campos = ['averbacao','desaverbacao','conf_av_desav','ctc','conf_ctc','dtc','conf_dtc','in_68','dpor','registro_atos','ag_completar','outros']
    meses = ['Junho','Julho','Agosto','Setembro','Outubro','Novembro','Dezembro']
    totais_anuais = {m:{c:0 for c incampos} for m in meses}
    producoes = LinhaProducao.query.filter(LinhaProducao.mes.in_(meses)).all()
    for p in producoes:
        for c in campos:
            if getattr(p,c): totais_anuais[p.mes][c]+=1
    grafico_anos = {c: sum(t[c] for t in totais_anuais.values()) for c incampos}
    return render_template('acompanhamento_anual.html', totais_anuais=totais_anuais, grafico_anos=grafico_anos, meses=meses, campos=campos)

# --- Painel Gerente ---
@app.route('/painel-gerente', methods=['GET','POST'])
@login_required
def painel_gerente():
    if current_user.tipo=='analista':
        flash('Acesso não autorizado.')
        return redirect(url_for('login'))
    analistas_presencial = Usuario.query.filter_by(tipo='analista', modalidade='presencial').all()
    analistas_tele = Usuario.query.filter_by(tipo='analista', modalidade='teletrabalho').all()
    analista_id = request.args.get('analista_id') or request.form.get('analista_id')
    user_sel = Usuario.query.get(analista_id) if analista_id else None

    meses = ['Junho','Julho','Agosto','Setembro','Outubro','Novembro','Dezembro']
    mes = request.args.get('mes') or request.form.get('mes') or meses[0]
    ano=2025
    idx = meses.index(mes)
    semanas= gerar_semanas(idx+6,ano)
    linhas = 33 if user_sel and user_sel.modalidade=='teletrabalho' else 28
    campos_chk = ['averbacao','desaverbacao','conf_av_desav','ctc','conf_ctc','dtc','conf_dtc','in_68','dpor','registro_atos','ag_completar','outros']
    totais, processos_info, alertas = {}, {}, {}
    total_feito = 0; percentual_meta=0; meta=100

    if user_sel:
        meta = 112 if user_sel.modalidade=='teletrabalho' else 100
        if request.method=='POST':
            for s in semanas:
                for i in range(linhas):
                    p = LinhaProducao.query.filter_by(usuario_id=user_sel.id, mes=mes, semana=s).offset(i).first()
                    if not p:
                        p = LinhaProducao(usuario_id=user_sel.id, mes=mes, semana=s, indice_linha=i, data_registro=datetime.utcnow())
                        db.session.add(p)
                    p.numero_processo = request.form.get(f'{s}_{i}_numero_processo') or ""
                    p.requerente = request.form.get(f'{s}_{i}_requerente') or ""
                    p.fase       = request.form.get(f'{s}_{i}_fase') or ""
                    for c in campos_chk:
                        setattr(p,c, bool(request.form.get(f'{s}_{i}_{c}')))
                    p.observacao = request.form.get(f'{s}_{i}_obs') or ""
            db.session.commit()
            flash('Produção atualizada.')
            return redirect(url_for('painel_gerente',analista_id=user_sel.id,mes=mes))

        processos_info = {
            s: [LinhaProducao.query.filter_by(usuario_id=user_sel.id, mes=mes, semana=s).offset(i).first() for i in range(linhas)]
            for s in semanas
        }
        totais = {s:{c:0 for c incampos_chk} for s in semanas}
        for s in semanas:
            prods = LinhaProducao.query.filter_by(usuario_id=user_sel.id, mes=mes, semana=s).all()
            for p in prods:
                for c in campos_chk:
                    if getattr(p,c): totais[s][c]+=1

        total_feito = sum(sum(v.values()) for v in totais.values())
        percentual_meta = min(int((total_feito/meta)*100),100)
        for s in semanas:
            faltam = (25 if user_sel.modalidade=='presencial' else 28) - sum(totais[s].values())
            if faltam>0: alertas[s]=f"Faltam {faltam} tarefas"

    # Totais anuais
    totais_anuais = {m:{c:0 for c incampos_chk} for m in meses}
    for m in meses:
        for p in LinhaProducao.query.filter_by(mes=m).all():
            for c incampos_chk:
                if getattr(p,c): totais_anuais[m][c]+=1

    return render_template('painel_gerente.html',
        analistas_presencial=analistas_presencial,
        analistas_tele=analistas_tele,
        usuario_selecionado=user_sel,
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

# --- Registro de Produção (Analistas) ---
@app.route('/registrar-producao', methods=['GET','POST'])
@login_required
def registrar_producao():
    if current_user.tipo!='analista':
        flash('Acesso negado.')
        return redirect(url_for('login'))

    usuario = current_user
    meses = ['Junho','Julho','Agosto','Setembro','Outubro','Novembro','Dezembro']
    ano=2025
    mes_param = request.args.get('mes') or meses[0]
    mes_atual = mes_param if mes_param in meses else meses[0]
    idx=meses.index(mes_atual)
    mes_anterior = meses[idx-1] if idx>0 else meses[-1]
    mes_posterior= meses[idx+1] if idx<len(meses)-1 else meses[0]
    semanas = gerar_semanas(idx+6, ano)
    linhas = 33 if usuario.modalidade=='teletrabalho' else 28
    campos = ['averbacao','desaverbacao','conf_av_desav','ctc','conf_ctc','dtc','conf_dtc','in_68','dpor','registro_atos','ag_completar','outros']

    if request.method=='POST':
        for s in semanas:
            for i in range(linhas):
                ind = i+1
                p = LinhaProducao.query.filter_by(usuario_id=usuario.id, mes=mes_atual, semana=s, indice_linha=ind).first()
                if not p:
                    p = LinhaProducao(usuario_id=usuario.id, mes=mes_atual, semana=s, indice_linha=ind, data_registro=datetime.utcnow())
                    db.session.add(p)
                for c in campos:
                    setattr(p,c, bool(request.form.get(f'{s}_{i}_{c}')))
                p.observacao = request.form.get(f'{s}_{i}_obs') or ""
        db.session.commit()
        flash('Produção salva.')
        return redirect(url_for('registrar_producao',mes=mes_atual))

    processos_info = {
        s: [LinhaProducao.query.filter_by(usuario_id=usuario.id, mes=mes_atual, semana=s, indice_linha=i+1).first() for i in range(linhas)]
        for s in semanas
    }
    totais = {s:{c:0 for c incampos} for s in semanas}
    for s in semanas:
        for p in LinhaProducao.query.filter_by(usuario_id=usuario.id, mes=mes_atual, semana=s).all():
            for c incampos:
                if getattr(p,c): totais[s][c]+=1
    total_feito = sum(sum(v.values()) for v in totais.values())
    meta = 112 if usuario.modalidade=='teletrabalho' else 100
    percentual_meta = min(int((total_feito/meta)*100),100)

    return render_template('registrar_producao.html',
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

# --- Acompanhamento Pessoal ---
@app.route('/acompanhamento-pessoal')
@login_required
def acompanhamento_pessoal():
    if current_user.tipo!='analista':
        flash('Acesso negado.')
        return redirect(url_for('login'))
    usuario = current_user
    mes = datetime.now().strftime('%B').capitalize()
    semanas = gerar_semanas(datetime.now().month, datetime.now().year)
    campos = ['averbacao','desaverbacao','conf_av_desav','ctc','conf_ctc','dtc','conf_dtc','in_68','dpor','registro_atos','ag_completar','outros']

    totais = {}
    total_feito = 0
    for s in semanas:
        cont = {c:0 for c incampos}
        for p in LinhaProducao.query.filter_by(usuario_id=usuario.id, semana=s, mes=mes).all():
            for c incampos:
                if getattr(p,c):
                    cont[c]+=1
                    total_feito+=1
        totais[s]=cont

    meta = 112 if usuario.modalidade=='teletrabalho' else 100
    percentual_meta = round((total_feito/meta)*100,1) if meta>0 else 0

    return render_template('acompanhamento_pessoal.html',
        usuario=usuario,
        semanas=semanas,
        totais=totais,
        campos=campos,
        total_feito=total_feito,
        meta=meta,
        percentual_meta=percentual_meta,
        mes=mes
    )

# --- Painel Estagiárias ---
@app.route('/painel-estagiarias', methods=['GET','POST'])
@login_required
def painel_estagiarias():
    if current_user.tipo!='estagiaria':
        flash('Acesso não autorizado.')
        return redirect(url_for('login'))
    analistas_presencial = Usuario.query.filter_by(tipo='analista', modalidade='presencial').all()
    analistas_tele = Usuario.query.filter_by(tipo='analista', modalidade='teletrabalho').all()
    analista_id = request.args.get('analista_id') or request.form.get('analista_id')
    user_sel = Usuario.query.get(analista_id) if analista_id else None

    meses = ['Junho','Julho','Agosto','Setembro','Outubro','Novembro','Dezembro']
    mes = request.args.get('mes') or request.form.get('mes') or meses[0]
    idx=meses.index(mes)
    semanas=gerar_semanas(idx+6,2025)
    linhas = 33 if user_sel and user_sel.modalidade=='teletrabalho' else 28
    campos_txt=['numero_processo','requerente','fase']
    campos_chk=['averbacao','desaverbacao','conf_av_desav','ctc','conf_ctc','dtc','conf_dtc','in_68','dpor','registro_atos','ag_completar','outros']

    if request.method=='POST' and user_sel:
        for s in semanas:
            for i in range(linhas):
                p = LinhaProducao.query.filter_by(usuario_id=user_sel.id, mes=mes, semana=s).offset(i).first()
                if not p:
                    p = LinhaProducao(usuario_id=user_sel.id, mes=mes, semana=s, indice_linha=i, data_registro=datetime.utcnow())
                    db.session.add(p)
                p.numero_processo = request.form.get(f'{s}_{i}_numero_processo') or ""
                p.requerente       = request.form.get(f'{s}_{i}_requerente')       or ""
                p.fase             = request.form.get(f'{s}_{i}_fase')             or ""
                p.observacao       = request.form.get(f'{s}_{i}_obs')              or ""
                for c in campos_chk:
                    setattr(p,c, bool(request.form.get(f'{s}_{i}_{c}')))
        db.session.commit()
        flash('Edições salvas.')

    processos_info = {}
    if user_sel:
        processos_info = {
            s:[LinhaProducao.query.filter_by(usuario_id=user_sel.id, mes=mes, semana=s).offset(i).first() for i in range(linhas)]
            for s in semanas
        }

    return render_template('painel_estagiarias.html',
        analistas_presencial=analistas_presencial,
        analistas_tele=analistas_tele,
        user_sel=user_sel,
        semanas=semanas,
        linhas=linhas,
        campos_txt=campos_txt,
        campos_chk=campos_chk,
        processos_info=processos_info,
        mes=mes
    )

# --- Relatório Geral ---
@app.route('/relatorio-geral')
@login_required
def relatorio_geral():
    if current_user.tipo=='analista':
        flash('Acesso negado.')
        return redirect(url_for('login'))
    ano=2025
    meses=['Junho','Julho','Agosto','Setembro','Outubro','Novembro','Dezembro']
    campos=['averbacao','desaverbacao','conf_av_desav','ctc','conf_ctc','dtc','conf_dtc','in_68','dpor','registro_atos','ag_completar','outros']
    totais_gerais={m:{c:0 for c incampos} for m in meses}
    for m in meses:
        for p in LinhaProducao.query.filter_by(mes=m).all():
            for c incampos:
                if getattr(p,c): totais_gerais[m][c]+=1

    return render_template('relatorio_geral.html', totais_gerais=totais_gerais, campos=campos, meses=meses)

# --- Editar produção individual ou em lote ---
@app.route('/editar-producao/<int:id>', methods=['GET','POST'])
@login_required
def editar_producao(id):
    if current_user.tipo!='gerente':
        flash('Acesso negado.')
        return redirect(url_for('login'))
    p = LinhaProducao.query.get_or_404(id)
    if request.method=='POST':
        p.numero_processo = request.form['numero_processo']
        p.requerente     = request.form['requerente']
        p.fase           = request.form['fase']
        db.session.commit()
        return redirect(url_for('painel_gerente'))
    return render_template('editar_producao.html', producao=p)

@app.route('/editar-producao-lote/<int:analista_id>', methods=['POST'])
@login_required
def editar_producao_lote(analista_id):
    if current_user.tipo!='estagiaria':
        flash('Acesso negado.')
        return redirect(url_for('login'))
    user = Usuario.query.get_or_404(analista_id)
    mes = request.args.get('mes') or 'Junho'
    ano=2025
    semanas=gerar_semanas(['Junho','Julho','Agosto','Setembro','Outubro','Novembro','Dezembro'].index(mes)+6,ano)
    linhas=33 if user.modalidade=='teletrabalho' else 28
    for s in semanas:
        for i in range(linhas):
            p = LinhaProducao.query.filter_by(usuario_id=analista_id, mes=mes, semana=s).offset(i).first()
            if not p:
                p = LinhaProducao(usuario_id=analista_id, mes=mes, semana=s, indice_linha=i, data_registro=datetime.utcnow())
                db.session.add(p)
            p.numero_processo = request.form.get(f'{s}_{i}_numero_processo') or ""
            p.requerente       = request.form.get(f'{s}_{i}_requerente')       or ""
            p.fase             = request.form.get(f'{s}_{i}_fase')             or ""
    db.session.commit()
    flash('Edições em lote salvas.')
    return redirect(url_for('painel_estagiarias', analista_id=analista_id, mes=mes))

# --- Filter util ---
@app.template_filter('get_attr')
def get_attr(obj, name):
    return getattr(obj, name, None)

if __name__ == '__main__':
    app.run(debug=True)
