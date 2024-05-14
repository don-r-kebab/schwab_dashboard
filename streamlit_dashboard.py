import datetime
import sys
import json
import argparse

import schwab
from schwab.client.base import BaseClient
import yaml
import streamlit as st
from streamlit_autorefresh import st_autorefresh

from account import AccountList
from states import states
import schwabdata
from datastructures import Config



ACCOUNT_FIELDS = BaseClient.Account.Fields




with open("dashboard_config.yaml", 'r') as dconf_fh:
    dashconfig = yaml.load(dconf_fh, Loader=yaml.Loader)
#print(dashconfig)

## Settings commands

REFRESH_TIME_MS = 1000*dashconfig['streamlit']['refreshtimer']
refresh_count = 0
if dashconfig['streamlit']['widelayout'] is True:
    st.set_page_config(layout="wide")
st_autorefresh(interval=REFRESH_TIME_MS, limit=None, key="dashboard_referesh_timer")


#### Globals

CONFIG: Config = Config()
APP_CONFIG = None

CONTRACT_TYPE = schwab.client.Client.Options.ContractType
ORDER_STATUS = schwab.client.Client.Order.Status
FIELDS = schwab.client.Client.Account.Fields
TRANSACTION_TYPES = schwab.client.Client.Transactions.TransactionType


st.session_state[states.CONFIG] = CONFIG


def sidebar_account_info(
        account_json = None
):
    with st.sidebar:
        if account_json is not None:
            with st.expander(
                    "Account Stats",
                    expanded=True
            ):
                sa = account_json['securitiesAccount']
                cb = sa['currentBalances']

                nlv = cb['liquidationValue']
                try:
                    bp_available = cb['buyingPowerNonMarginableTrade']
                except KeyError as ke:
                    try:
                        bp_available = cb['cashAvailableForTrading']
                    except KeyError:
                        pass
                bpu = (1.0-bp_available/nlv)*100
                st.write(f"NLV: {nlv}")
                st.write(f"BP Available: {bp_available}")
                st.write(f"BPu: {(bpu):.2f}%")
        else:
            st.write("Failed to get Account Info")

def get_schwab_client(conf: Config = None):
    c = conf
    if c is None:
        if states.CONFIG in st.session_state:
            c = st.session_state[states.CONFIG]
        else:
            raise Exception("Unable to create client")
    if c is not None:
        sys.stderr.write(json.dumps(c.__dict__, indent=4))
        return schwab.auth.easy_client(
            c.apikey,
            c.apisecretkey,
            c.callbackuri,
            c.tokenpath
        )
    else:
        raise Exception("Unable to create client")


def make_todays_stats(
        con: st.container,
        client = None,
        config: Config = None
):
    print("Getting today's stats")
    with con:
        st.header("Today's Stats")
        if client is None:
            try:
                client = get_schwab_client(config)
            except Exception as e:
                raise e
        try:
            #if states.ORDERS_JSON not in st.session_state:
            st.session_state[states.ORDERS_JSON] = schwabdata.get_todays_orders(
                st.session_state[states.ACTIVE_HASH],
                conf=config,
                client=client
            )
            order_json = st.session_state[states.ORDERS_JSON]
            positions_json = st.session_state[states.POSITIONS_JSON]
            account_json = st.session_state[states.ACCOUNTS_JSON]
        except Exception as e:
            print(e)
            raise e

            #if states.ACCOUNTS_JSON not in st.session_state:
        #st.json(order_json[4])
        todays_premium = schwabdata.get_order_option_premium(order_json)
        #st.stop()
        tp_display = todays_premium*100

        sa = account_json['securitiesAccount']
        cb = sa['currentBalances']
        ib = sa['initialBalances']

        current_nlv = cb['liquidationValue']
        initial_nlv = ib['liquidationValue']
        nlv_net = current_nlv - initial_nlv
        nlv_perc = nlv_net/initial_nlv
        bp_available = cb['buyingPowerNonMarginableTrade']
        bp_perc = bp_available/current_nlv
        todays_percent = tp_display/initial_nlv

        #todays_premium = round(schwabdata.get_order_option_premium(order_json)*100,2)
        if todays_premium is None:
            todays_premium = 0
        #todays_pct = round(todays_premium/adata.nlv * 100,2)
            #order_counts = schwabdata.get_order_count(client, conf)
        col_1, col_2, col3 = st.columns(3)
        col_1.write("NLV:")
        col_2.write(f"{current_nlv}")
        col3.write(f"{(nlv_perc*100):.2f}%")
        col_1.write("Today's Premium:")
        col_2.write(f"{tp_display}")
        col3.write(f"{(todays_percent*100):.2f}%")
        #col_2.write("\t{} ({}%)".format(todays_premium, todays_pct))
        #col1.write("Today's Orders:")
        #col_2.write("\t{}".format(order_counts))


def __account_change(client=None):
    aa = st.session_state[states.ACTIVE_ACCOUNT]
    conf = st.session_state[states.CONFIG]
    st.session_state = {
        states.ACTIVE_ACCOUNT: aa,
        states.CONFIG: conf
    }
    return


def position_filtering(con: st.container):
    with con:
        st.title("RED ALERT")
        filter_field = st.selectbox(
            "Filter",
            ["%OTM"]
        )
        red_alert_df = schwabdata.get_pos_df().drop(columns=['ctype', 'symbol'])
        if filter_field == "%OTM":
            pass
            otm_select_values = ("40", "35", "30", "25", "20", "15", "10")
            min_otm_select_value = st.selectbox(
                "Min Percent OTM",
                otm_select_values,
                index=2
            )
            min_otm = int(min_otm_select_value)/100.0
            #print(min_otm)
            st.dataframe(
                red_alert_df.loc[red_alert_df['otm'] < min_otm, :]
            )






def sidebar_account_select(
        alist: AccountList=None,
        default_account=None
):
    with st.sidebar:
        anum_list = [None]
        anum_list.extend(alist.get_account_numbers())
        if default_account is not None:
            default_index = anum_list.index(default_account)
        else:
            default_index = 0
        st.session_state[states.ACTIVE_ACCOUNT] = st.selectbox(
            "Account Select",
            anum_list,
            index=default_index,
            on_change=__account_change
            #kwargs={"client": None}
            #on_change=st.rerun
        )
    return






def main(**argv):
    conf: Config = CONFIG
    #st.json(conf.__dict__)
    st.cache_data(ttl=dashconfig['streamlit']['refreshtimer'])
    client = schwab.auth.easy_client(conf.apikey, conf. apisecretkey, conf.callbackuri, conf.tokenpath)
    accounts_json = client.get_account_numbers().json()
    alist = AccountList(jdata=accounts_json)
    st.session_state[states.ACCOUNT_LIST] = alist
    acc_json = None
    sidebar_account_select(alist, default_account=conf.defaultAccount)
    if states.ACTIVE_ACCOUNT not in st.session_state or st.session_state[states.ACTIVE_ACCOUNT] is None:
        st.write("Please Select an account")
        st.stop()
    st.session_state[states.ACTIVE_HASH] = alist.get_hash(st.session_state[states.ACTIVE_ACCOUNT])
    acc_json = client.get_account(account_hash=st.session_state[states.ACTIVE_HASH], fields=[ACCOUNT_FIELDS.POSITIONS]).json()
    st.session_state[states.ACCOUNTS_JSON] = acc_json
    #st.json(acc_json)
    st.session_state[states.POSITIONS_JSON] = acc_json['securitiesAccount']['positions']
    #st.json(st.session_state[states.POSITIONS_JSON])
    sidebar_account_info(account_json=acc_json)

    st.header("Schwab Position Tracker")
    st.write(f"Update time: {datetime.datetime.now()}")

    stats = st.expander("Today's Stats", expanded=True)
    sut_test_con = st.expander("SUT test", expanded=True)
    premium_by_ticker = st.expander("Premium By Ticker", expanded=True)
    pos_filter_con = st.expander("RED ALERT - position review", expanded=True)


    make_todays_stats(stats, client=client)
    position_filtering(pos_filter_con)
    #st.json(schwabdata.get_todays_orders(ahash=st.session_state[states.ACTIVE_HASH], conf=CONFIG).text)
    #st.write(schwabdata.get_todays_orders(ahash=states.ACTIVE_ACCOUNT_HASH, conf=CONFIG).text)


    #def get_positions_json(config: Config):
    #    acc_json = client.get_account(config.accountnum, fields=[ACCOUNT_FIELDS.POSITIONS]).json()
    #    accdata = acc_json['securitiesAccount']
    #    positions = accdata['positions']
   #     return positions

#def get_display_df(ad: AccountData, index: list =["Stats"]):
#    d = {}
#    d['NLV'] = ad.nlv
#    d['BPu'] = ad.bpu
#    d['Buying Power'] = ad.bp_available
#    d['Short Unit Max'] = ad.sutmax
#    df = pd.DataFrame(d, index=index)
#    return df




if __name__ == '__main__':
    print("Starting LottoBuddy")
    CONFIG = Config()
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--appconfig",
        dest="appconfig",
        default="dashboard_config.yaml"
    )
    # This is intended to enabling/disabling auto-refresh on dashboard
    # Currently not implemented and is hard coded to be true
    ap.add_argument("--update", default=False, action="store_true")
    args = vars(ap.parse_args())
    with open(args['appconfig'], 'r') as ac_fh:
        APP_CONFIG = yaml.safe_load(ac_fh)
    CONFIG.read_config(APP_CONFIG['schwab']['configfile'])
    st.session_state[states.CONFIG_FILE] = APP_CONFIG['schwab']['configfile']
    st.session_state[states.TOKEN_FILE] = APP_CONFIG['schwab']['tokenfile']
    st.session_state[states.CONFIG] = CONFIG
    main(**args)
