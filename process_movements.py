from fintoc import Fintoc
import datetime as dt
import pandas as pd
import re
from thefuzz import fuzz
from thefuzz import process

def get_dataframe_movements_for_link_tokens(link_tokens, since, until, fintoc_client):
    links_accounts_movements = []
    for link_token in link_tokens:
        link = fintoc_client.links.get(link_token)
        print(f'| Getting accounts for link {link.id} ({link.institution.name} <{link.holder_id}>)')
        for account in link.accounts.all():
            print(f'|-- Gettings movements for account {account.number} <{account.type}>')
            for movement in account.movements.all(since = since, until = until):
                try:
                    links_accounts_movements.append(dict(
                        #link
                        link_id = link.id,
                        link_institution_name=link.institution.name,
                        link_holder_id = link.holder_id,
                        
                        #account
                        account_type=account.type,
                        account_number=account.number,
                        account_holder_id=account.holder_id,
                        account_holder_name=account.holder_name,
                        #movement
                        id=movement.id,
                        description=movement.description,
                        amount=movement.amount,
                        currency=movement.currency,
                        post_date=movement.post_date,
                        transaction_date=movement.transaction_date,
                        type=movement.type,
                        recipient_account_holder_id=movement.recipient_account.holder_id if movement.recipient_account is not None else None,
                        recipient_account_holder_name=movement.recipient_account.holder_name if movement.recipient_account is not None else None,
                        comment=movement.comment,
                    ))
                except Exception as e:
                    print(movement.serialize())
                    raise e
        print('\t')
    return pd.DataFrame.from_dict(links_accounts_movements)

def categorize_movement(movement):
    patterns = {
        r'.*SEGURO.*|.*DESGRAVAMEN.*' : 'Seguros',
        r'PAGO.*TAR.*CRED.*|.*T\. CRÉDITO.*|.*TARJETA DE C.*|.*DEUDA INTERNACIO.*|.*MONTO CANCELADO.*': 'Pago de Tarjeta de Crédito',
        r'TRANSF.*|.*TRASPASO.*': 'Transferencias a terceros',
        r'D\d{11} \d{3}/\d{3}|PAGO CUOTA CREDITO.*|PAGO.*CREDITO.*|.*HIPOTEC.*|.*L.CREDITO.*|.*CREDITO.*|.*PRESTAMO.*|.*L.*NEA.*CR.*DITO.*' : 'Créditos',
        r'COMPRA.*' : 'Compras',
        r'.*DE SERVICIOS|.*PAGO.*CUENTA.*|.*PAGO EN LINEA.*' : 'Cuentas y Servicios',
        r'IMPUESTO.*|.*IMPTO.*': 'Impuestos',
        r'.*COMISION.*|.*INTERESES.*': 'Comisiones e Intereses',
        r'P\.PROVEEDOR.*|.*PAGO RECIBIDO.*':'Cuentas y Servicios',
        r'.*MONEX.*|.*DIVI.*|INVERSION.*|.*DAP.*|.*FFMM.*|.*ACCIONES.*|.*RESCATE.*|.*DEPOSITO A PLAZO.*|.*ALCANCIA.*': 'Inversiones',
        r'REMUNE.*|SALARIO.*|PAGO NOMINA.*': 'Remuneraciones',
        r'GIRO.*|.*ATM.*': 'Retiros por Caja o ATM',
        r'.*CHEQUE.*|.*DOCUMENTO.*|.*VALE.*VISTA.*': 'Cheque, Documento y Valevistas',
    }
    description = movement['description'].upper()
    
    if movement['type'] == 'transfer':
        if re.search(re.compile(r'.*FINTUAL.*|.*RACIONAL.*|.*ALCANCIA.*'), description):
            return 'Inversiones'
        if (movement.link_holder_id == movement.recipient_account_holder_id
            or str(movement.account_holder_id) in re.sub(r'[A-z -]', r'', description)
            or re.search(re.compile(r'.*CUENTA.*PROPIA.*'), description)):
            
            return 'Transferencias entre cuentas propias'
        return 'Transferencias a terceros'

    if movement['account_type'] in ('checking_account', 'sight_account'):
        for pattern, category in patterns.items():
            if re.search(re.compile(pattern), description):
                return category
    return 'Otros'

def get_own_account_desc_for_holder_name(holder_names, glosas):
    own_account_descriptions = []
    for holder_name in holder_names:
        for glosa in glosas:
            result = fuzz.ratio(re.sub(r'[^A-z ]+', r'', holder_name).upper().strip(),
                       re.sub(r'[^A-z ]+', r'', glosa).upper().strip().replace('TRANSF', '').replace("TEF", ''))
            if result > 50:
                own_account_descriptions.append(glosa.upper())
    return list(set(own_account_descriptions))

def is_own_account_description(description, compare_list):
    if len(process.extractBests(description.upper(),
                                compare_list, 
                                score_cutoff=80, 
                                limit = 1, 
                                scorer=fuzz.ratio)
          ) > 0:
        return True
    return False

def categorize_product_movement(movement):
    patterns = {
        r'.*PAC.*' : 'PAC',
        r'.*PAT.*' : 'PAT',
        r'TRANSF.*|.*TRASPASO.*': 'Transferencias',
        r'DIVIDEN.*|.*HIPOTEC.*': 'Credito Hipotecario',
        r'.*CONSUMO.*': 'Crédito de Consumo',
        r'.*L.CREDITO.*|.*L.*NEA.*CR.*DITO.*': 'Línea de Crédito',
        r'.*T\. CRÉDITO.*|.*TARJETA DE C.*': 'Tarjeta de Crédito',
        r'.*MONEX.*|.*DIVISA.*': 'Compra y venta de divisas',
        r'.*DAP.*|.*DEPOSITO A PLAZO.*': 'DAP',
        r'.*ALCANCIA.*': 'Cuenta Ahorro',
        r'.*FFMM.*': 'FFMM',
        r'.*ATM.*': 'Cajero',
        r'.*PAGO.*CAJA.*': 'Caja',
        r'.*ACCIONES.*': 'ACCIONES',
        r'.*CHEQUE.*|.*DOCUMENTO.*|.*VALE.*VISTA.*': 'Documentos',
        r'REMUNE.*|SALARIO.*|PAGO NOMINA.*|.*P\.PROVEEDOR.*|.*PAGO RECIBIDO.*|.*DE SERVICIOS|.*PAGO.*CUENTA.*|.*PAGO EN LINEA.*': 'Pagos masivos y convenios',
    }
    description = movement['description'].upper()
        
    if movement['account_type'] in ('checking_account', 'sight_account'):
        for pattern, category in patterns.items():
            if re.search(re.compile(pattern), description):
                return category

    if movement['type'] == 'transfer':
        return 'Transferencias'
    
    elif movement['account_type'] == 'credit_card':
        return 'Tarjeta de Crédito'
    
    return 'Otros'

def get_monthly_income_df(movements_df):
    renta = movements_df[movements_df.category == 'Remuneraciones'][['post_date', 'year_month', 'amount']].copy()
    observations = len(renta.groupby(['year_month']).amount.sum())
    estimated_rolling = max(min(12, round(observations/12)*3), 1)
    
    print(f"Found {observations} observations, using {estimated_rolling} periods for rolling window.")
    
    idx = pd.date_range(renta.post_date.min(), dt.date.today(), freq = 'D')
    renta.index = pd.DatetimeIndex(renta.post_date)
    renta.reindex(idx, fill_value=0)
    renta = renta[['amount']]
    renta['year_month'] = renta.index.to_series().apply(lambda x: x.strftime('%Y%m'))
    monthly_income_df = pd.DataFrame(renta.groupby(['year_month']).amount.sum())
    monthly_income_df['median_amount'] = monthly_income_df['amount'].rolling(estimated_rolling).median()
    monthly_income_df['median_amount_diff'] = abs(monthly_income_df['median_amount'].diff(-1))
    
    return monthly_income_df.dropna(subset=["median_amount"])

def analyze_income_raise_events(_income_df):
    income_df = _income_df.copy()
    ## obtenemos los outliers sobre la diferencia de la mediana
    income_df['has_raise_event'] = pd.qcut(abs(income_df['median_amount_diff']), 4, labels = False, duplicates='drop')
    income_df['has_raise_event'] = income_df['has_raise_event'].fillna('NO')
    income_df['has_raise_event'] = income_df['has_raise_event'].replace(0, 'NO')
    income_df['has_raise_event'] = income_df['has_raise_event'].replace(1, 'NO')
    income_df['has_raise_event'] = income_df['has_raise_event'].replace(2, 'YES')
    income_df['has_raise_event'] = income_df['has_raise_event'].replace(3, 'YES')
    
    income_df.loc[income_df.has_raise_event == 'YES', 'event_id'] = income_df['has_raise_event'].ne(income_df['has_raise_event'].shift()).cumsum()
    income_df.event_id = income_df.event_id.rank(method='dense').fillna(0).astype(int)
    
    ## sobre cada outlier hay que identificar los outliers consecutivos y acumular esos montos para sacar los cambios reales
    income_df['event_id_obs'] = income_df.groupby('event_id').event_id.transform('rank', method='first').astype(int)
    income_df['raise_event_amount'] = income_df.groupby('event_id')['median_amount_diff'].cumsum()
    
    ## sacamos todos los valores acumulados de los que no correspondan al ultimo cambio respecto a cada evento
    idx = income_df.groupby(['event_id'])['event_id_obs'].transform(max) != income_df['event_id_obs']
    income_df.loc[idx, 'raise_event_amount'] = 0
    
    ## rellenamos nulls
    income_df['raise_event_amount'] = income_df['raise_event_amount'].fillna(0).astype(int)
    income_df['median_amount'] = income_df['median_amount'].fillna(0).astype(int)
    income_df['median_amount_diff'] = income_df['median_amount_diff'].fillna(0).astype(int)
    
    print(f"Detected {max(income_df.event_id.max(), 0)} raise events")
    
    return income_df

def get_pivoted_data(df, add_grand_total = True):
    res = df.groupby(['year_month', 'category']).sum().pivot_table(index=['year_month'],
                                                                columns='category',
                                                                values='amount',
                                                                aggfunc='first').reset_index().fillna(0)
    if add_grand_total:
        res['Total'] = res.sum(numeric_only = True, axis=1)
        
    return res

def get_df_with_numerics_rolling_median(df):
    numerics = ['int16', 'int32', 'int64', 'float16', 'float32', 'float64']
    estimated_rolling = max(min(4, round(len(df)/4)*3), 1)

    selected_df = df.select_dtypes(include=numerics)
    renamed_cols = []
    for col in selected_df.columns:
        renamed_cols.append(col+ '_rolling_median')
    result_df = selected_df.rolling(estimated_rolling).median().fillna(0)
    result_df.columns = renamed_cols
    return df.join(result_df)

def get_monthly_savings_df(movements_df):
    df_savings = movements_df[(movements_df.category.isin(['Inversiones']))][['amount',
                                                                   'year_month',
                                                                   'post_date',
                                                                   'description',
                                                                   'category',
                                                                   'product',
                                                                   'flow']]
    df_savings['amount_sign'] = df_savings.apply(lambda x: -int(x['amount']) if x['flow'] == 'IN' else int(x['amount']), axis = 1)
    
    df_savings = df_savings.groupby(['post_date', 'year_month']).amount_sign.sum().reset_index()
    
    observations = len(df_savings)
    estimated_rolling = max(min(6, round(observations/6)*3), 1)
    
    print(f"Found {observations} observations, using {estimated_rolling} periods for rolling window.")
    
    idx = pd.date_range(df_savings.post_date.min(), dt.date.today(), freq = 'D')
    df_savings.index = pd.DatetimeIndex(df_savings.post_date)
    df_savings.reindex(idx, fill_value=0)
    
    df_savings = pd.DataFrame(df_savings.groupby(['year_month']).amount_sign.sum())
    df_savings['amount_sign'] =  df_savings['amount_sign'].apply(lambda x: 0 if x < 0 else x)
    df_savings['median_amount'] = df_savings['amount_sign'].rolling(estimated_rolling).median()
    df_savings['median_amount_diff'] = abs(df_savings['median_amount'].diff(-1))
    return df_savings.reset_index().copy()

def get_analytical_dataframes(fintoc_secret_key, link_tokens, since, until):
    fintoc_client = Fintoc(fintoc_secret_key)

    movements_df = get_dataframe_movements_for_link_tokens(link_tokens,
                                                        since=since,
                                                        until=until,
                                                        fintoc_client=fintoc_client)
    final_movements_df = movements_df.copy()
    final_movements_df['category'] = final_movements_df.apply(categorize_movement, axis = 1)
    final_movements_df['product'] = final_movements_df.apply(categorize_product_movement, axis = 1)
    final_movements_df['flow'] = final_movements_df.amount.apply(lambda x: 'IN' if x > 0 else 'OUT')
    final_movements_df['amount'] = final_movements_df.amount.apply(abs)
    final_movements_df['year_month'] = final_movements_df['post_date'].apply(lambda x: x.strftime('%Y%m'))

    ## fix para algunas tx que no quedan marcadas de cuentas propias
    best_holder_name =  max(list(final_movements_df.account_holder_name.unique()), key=len) ## se asume que es el mismo
    glosas = list(final_movements_df[final_movements_df.category == 'Transferencias entre cuentas propias'].description.unique())
    compare_list = get_own_account_desc_for_holder_name([best_holder_name], glosas) + [best_holder_name]

    final_movements_df.loc[final_movements_df.category == 'Transferencias a terceros', 'category'] =\
        final_movements_df.loc[final_movements_df.category == 'Transferencias a terceros'].apply(lambda x:'Transferencias entre cuentas propias' if is_own_account_description(x['description'], compare_list) else x['category'], axis =1)
    
    # buscamos los espejos de movimientos realizados en un mismo dia y si resulta que nos cuadra por (monto,fecha,flow)
    # que existe un movimiento entre cuenta propia y otro a terceros, imputamos el de tercero a cuenta propia
    final_movements_df.loc[final_movements_df[(final_movements_df['product'].isin(['Transferencias']))]\
                    .groupby(['post_date', 'amount']).filter(lambda x: x['flow'].count() == 2
                                                                and len(list(x['flow'].unique())) == 2
                                                                and len(list(x['category'].unique())) == 2
                                                                and ('180257578' in list(x['recipient_account_holder_id'])
                                                                    or not x['recipient_account_holder_id'].any())
                                                            ).index, 'category']\
    = 'Transferencias entre cuentas propias'
    
    income_df = get_monthly_income_df(final_movements_df)
    income_events_df = analyze_income_raise_events(income_df)

    df_ingress = final_movements_df[(final_movements_df.flow == 'IN')&
                                ~(final_movements_df.category.isin(['Transferencias entre cuentas propias']))
                               ][['amount',
                                                              'year_month',
                                                               'post_date',
                                                               'description',
                                                               'category',
                                                               'product',
                                                               'flow']].sort_values(by=['category', 'flow'])

    df_egress = final_movements_df[(final_movements_df.flow == 'OUT')&
                        ~(final_movements_df.category.isin(['Transferencias entre cuentas propias']))][['amount',
                                                                'year_month',
                                                                'post_date',
                                                                'description',
                                                                'category',
                                                                'product',
                                                                'flow']].sort_values(by=['category', 'flow'])
    df_ingress_income = final_movements_df[(final_movements_df.flow == 'IN')&
                   (final_movements_df.category.isin(['Transferencias a terceros', 'Remuneraciones']))][['amount',
                                                              'year_month',
                                                               'post_date',
                                                               'description',
                                                               'category',
                                                               'product',
                                                               'flow']].sort_values(by=['category', 'flow'])

    df_spendings = final_movements_df[(final_movements_df.flow == 'OUT')&
                    ~(final_movements_df.category.isin(['Transferencias entre cuentas propias', 'Inversiones', 'Créditos']))][['amount',
                                                                'year_month',
                                                                'post_date',
                                                                'description',
                                                                'category',
                                                                'product',
                                                                'flow']].sort_values(by=['category', 'flow'])
    df_mortgage = final_movements_df[(final_movements_df.flow == 'OUT')&
                   (final_movements_df.category.isin(['Créditos', 'Pago de Tarjeta de Crédito']))][['amount',
                                                               'year_month',
                                                               'post_date',
                                                               'description',
                                                               'category',
                                                               'product',
                                                               'flow']].sort_values(by=['category', 'flow'])
    final_df_savings = get_monthly_savings_df(final_movements_df)[['year_month', 'amount_sign', 'median_amount']]

    final_df_income = income_events_df[['amount', 'median_amount', 'raise_event_amount']].reset_index(False)

    final_df_mortgage = get_df_with_numerics_rolling_median(get_pivoted_data(df_mortgage))

    final_df_spendings = get_df_with_numerics_rolling_median(get_pivoted_data(df_spendings))

    final_df_ingress_income = get_df_with_numerics_rolling_median(get_pivoted_data(df_ingress_income))

    final_df_ingress = get_df_with_numerics_rolling_median(get_pivoted_data(df_ingress))
    final_df_egress = get_df_with_numerics_rolling_median(get_pivoted_data(df_egress))
    
    final_view_monthly_ingress_egress = final_view_monthly_ingress.merge(final_view_monthly_egress, on = 'year_month').set_index("year_month")
    final_view_monthly_ingress_egress.columns = ['ingress', 'egress']

    return {
        'monthly_ingress_egress' : final_view_monthly_ingress_egress,
        'monthly_ingress' : final_df_ingress[['year_month', 'Total']],
        'monthly_spendings' : final_df_spendings[['year_month', 'Total', 'Total_rolling_median']],
        'monthly_savings' : final_df_savings[['year_month', 'median_amount']],
        'monthly_income' : final_df_income[['year_month', 'median_amount']],
        'monthly_mortgage' : final_df_mortgage[['year_month', 'Créditos_rolling_median']],
        'monthly_credit_card_usage' : final_df_mortgage[['year_month', 'Pago de Tarjeta de Crédito_rolling_median']],
    }