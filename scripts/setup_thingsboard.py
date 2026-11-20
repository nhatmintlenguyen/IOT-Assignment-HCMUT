#!/usr/bin/env python3
"""
Smart Safe Guardian - ThingsBoard Automated Setup & Provisioning Script
Configures Tenant, Admin, Gateway, Device, and complete Dashboard in 1 click.
"""

import copy
import json
import os
import random
import sys
import time
import requests

TB_URL = os.getenv("THINGSBOARD_URL", "http://localhost:8080")
SYSADMIN_USER = os.getenv("SYSADMIN_USER", "sysadmin@thingsboard.org")
SYSADMIN_PASS = os.getenv("SYSADMIN_PASS", "sysadmin")

TENANT_TITLE = "HCMUT Smart Safe"
TENANT_ADMIN_EMAIL = "admin@smartsafevault.com"
TENANT_ADMIN_PASS = "tenant"

DEVICE_NAME = "Smart Safe Guardian"
DEVICE_TOKEN = "6EzRR6gcTvnOcgVF53hP"

GATEWAY_NAME = "Smart Safe Gateway"


def login(username, password):
    resp = requests.post(f"{TB_URL}/api/auth/login", json={"username": username, "password": password})
    if resp.status_code == 200:
        return resp.json().get("token")
    return None


def get_or_create_tenant(sys_token):
    headers = {"X-Authorization": f"Bearer {sys_token}"}
    resp = requests.get(f"{TB_URL}/api/tenants?pageSize=50&page=0", headers=headers)
    if resp.status_code == 200:
        tenants = resp.json().get("data", [])
        for t in tenants:
            if t.get("title") == TENANT_TITLE:
                return t["id"]["id"]

    # Create tenant
    create_resp = requests.post(
        f"{TB_URL}/api/tenant",
        headers=headers,
        json={"title": TENANT_TITLE}
    )
    if create_resp.status_code == 200:
        return create_resp.json()["id"]["id"]
    raise RuntimeError(f"Failed to create tenant: {create_resp.text}")


def ensure_tenant_admin(sys_token, tenant_id):
    headers = {"X-Authorization": f"Bearer {sys_token}"}
    # Check if user can already log in
    if login(TENANT_ADMIN_EMAIL, TENANT_ADMIN_PASS):
        return

    # Check if user exists in tenant
    resp = requests.get(f"{TB_URL}/api/tenant/{tenant_id}/users?pageSize=20&page=0", headers=headers)
    user_id = None
    if resp.status_code == 200:
        for u in resp.json().get("data", []):
            if u.get("email") == TENANT_ADMIN_EMAIL:
                user_id = u["id"]["id"]
                break

    if not user_id:
        create_user_resp = requests.post(
            f"{TB_URL}/api/user?sendActivationMail=false",
            headers=headers,
            json={
                "tenantId": {"entityType": "TENANT", "id": tenant_id},
                "authority": "TENANT_ADMIN",
                "email": TENANT_ADMIN_EMAIL,
                "firstName": "SmartSafe",
                "lastName": "Admin"
            }
        )
        if create_user_resp.status_code == 200:
            user_id = create_user_resp.json()["id"]["id"]
        else:
            raise RuntimeError(f"Failed to create tenant admin: {create_user_resp.text}")

    # Activate user with password
    act_resp = requests.get(f"{TB_URL}/api/user/{user_id}/activationLink", headers=headers)
    if act_resp.status_code == 200:
        act_link = act_resp.text
        act_token = act_link.split("activateToken=")[-1].strip()
        requests.post(
            f"{TB_URL}/api/noauth/activate",
            json={"activateToken": act_token, "password": TENANT_ADMIN_PASS}
        )


def ensure_device(tenant_token, name, token, is_gateway=False):
    headers = {"X-Authorization": f"Bearer {tenant_token}"}
    # Search device
    resp = requests.get(f"{TB_URL}/api/tenant/devices?pageSize=50&page=0", headers=headers)
    dev_id = None
    if resp.status_code == 200:
        for d in resp.json().get("data", []):
            if d.get("name") == name:
                dev_id = d["id"]["id"]
                break

    if not dev_id:
        payload = {
            "name": name,
            "type": "default",
            "label": "IoT Gateway" if is_gateway else "YoloUNO Security Vault",
            "additionalInfo": {"gateway": is_gateway}
        }
        create_resp = requests.post(f"{TB_URL}/api/device", headers=headers, json=payload)
        if create_resp.status_code == 200:
            dev_id = create_resp.json()["id"]["id"]
        else:
            raise RuntimeError(f"Failed to create device {name}: {create_resp.text}")

    # Ensure credentials / token
    cred_resp = requests.get(f"{TB_URL}/api/device/{dev_id}/credentials", headers=headers)
    if cred_resp.status_code == 200:
        cred = cred_resp.json()
        if cred.get("credentialsId") != token:
            cred["credentialsType"] = "ACCESS_TOKEN"
            cred["credentialsId"] = token
            requests.post(f"{TB_URL}/api/device/credentials", headers=headers, json=cred)

    return dev_id


def get_system_widget_type(headers, fqn):
    r = requests.get(f"{TB_URL}/api/widgetType?isSystem=true&fqn={fqn}", headers=headers)
    if r.status_code == 200:
        d = r.json()
        return d.get("descriptor", {}).get("type"), json.loads(d.get("descriptor", {}).get("defaultConfig", "{}"))
    raise RuntimeError(f"Failed to fetch system widget type {fqn}: {r.text}")


def build_and_upload_dashboard(tenant_token, vault_device_id):
    headers = {"X-Authorization": f"Bearer {tenant_token}"}
    alias_id = "e7b0c510-e400-11f1-bf0b-ed890d705073"

    val_type, val_base_cfg = get_system_widget_type(headers, "system.cards.value_card")
    chart_type, chart_base_cfg = get_system_widget_type(headers, "system.time_series_chart")
    rpc_type, rpc_base_cfg = get_system_widget_type(headers, "system.control_widgets.rpcbutton")
    tbl_type, tbl_base_cfg = get_system_widget_type(headers, "system.cards.timeseries_table")
    sw_type, sw_base_cfg = get_system_widget_type(headers, "system.control_widgets.slide_toggle_control")

    def make_val(wid, title, key_name, units, decimals, icon, color, font_size=34, is_func_color=False, color_func="", post_func=None, size_x=3, size_y=4):
        cfg = copy.deepcopy(val_base_cfg)
        cfg["title"] = ""
        cfg["showTitle"] = False
        cfg["units"] = units
        cfg["decimals"] = decimals
        cfg["backgroundColor"] = "#121b2d"
        cfg["color"] = "#f8fafc"
        cfg["borderRadius"] = "14px"
        cfg["dropShadow"] = True
        cfg["widgetCss"] = ""

        s = cfg["settings"]
        s["autoScale"] = True
        s["showLabel"] = True
        s["labelPosition"] = "top"
        s["showIcon"] = True
        s["icon"] = icon
        s["labelFont"] = {"size": 13, "sizeUnit": "px", "family": "Roboto", "weight": "500", "style": "normal"}
        s["labelColor"] = {"type": "constant", "color": "#94a3b8"}

        if is_func_color:
            s["valueColor"] = {"type": "function", "color": color, "colorFunction": color_func}
            s["iconColor"] = {"type": "function", "color": color, "colorFunction": color_func}
        else:
            s["valueColor"] = {"type": "constant", "color": color}
            s["iconColor"] = {"type": "constant", "color": color}

        s["valueFont"] = {"family": "Roboto", "size": font_size, "sizeUnit": "px", "style": "normal", "weight": "600"}
        s["background"] = {
            "type": "color",
            "color": "#121b2d",
            "overlay": {
                "enabled": False,
                "color": "rgba(255,255,255,0.72)",
                "blur": 3
            }
        }
        s["showDate"] = True
        s["dateFormat"] = {"format": None, "lastUpdateAgo": True, "custom": False}
        s["dateColor"] = {"type": "constant", "color": "#64748b"}
        s["dateFont"] = {"family": "Roboto", "size": 11, "sizeUnit": "px", "style": "normal", "weight": "400"}

        dk = {
            "name": key_name,
            "type": "timeseries",
            "label": title,
            "color": color,
            "settings": {},
            "_hash": random.random(),
            "units": units,
            "decimals": decimals,
            "aggregationType": None,
            "funcBody": None,
            "usePostProcessing": bool(post_func),
            "postFuncBody": post_func or ""
        }

        cfg["datasources"] = [{
            "type": "entity",
            "name": "",
            "entityAliasId": alias_id,
            "dataKeys": [dk],
            "alarmFilterConfig": {"statusList": ["ACTIVE"]}
        }]
        return {
            "id": wid,
            "typeFullFqn": "system.cards.value_card",
            "type": val_type,
            "sizeX": size_x,
            "sizeY": size_y,
            "config": cfg
        }

    def make_chart(wid, title, keys):
        cfg = copy.deepcopy(chart_base_cfg)
        cfg["title"] = title
        cfg["showTitle"] = True
        cfg["titleStyle"] = {"color": "#ffffff", "fontSize": "15px", "fontWeight": "600"}
        cfg["titleColor"] = "#ffffff"
        cfg["backgroundColor"] = "#121b2d"
        cfg["color"] = "#ffffff"
        cfg["borderRadius"] = "14px"
        cfg["dropShadow"] = True
        cfg["widgetCss"] = ".tb-time-series-chart-widget th, .tb-time-series-chart-widget td, .tb-legend-header, .legend-header { color: #ffffff !important; opacity: 1 !important; }"

        def make_axis(aid, label, color, position, order, units='', decimals=0, show_split=False, min_val=None, max_val=None, interval=None, split_number=None):
            ax = {
                "id": aid,
                "order": order,
                "units": units,
                "decimals": decimals,
                "show": True,
                "label": label,
                "labelFont": {"family": "Roboto", "size": 11, "sizeUnit": "px", "style": "normal", "weight": "600", "lineHeight": "1"},
                "labelColor": color,
                "position": position,
                "showTickLabels": True,
                "tickLabelFont": {"family": "Roboto", "size": 11, "sizeUnit": "px", "style": "normal", "weight": "400", "lineHeight": "1"},
                "tickLabelColor": color,
                "ticksFormatter": None,
                "showTicks": True,
                "ticksColor": color,
                "showLine": True,
                "lineColor": color,
                "showSplitLines": show_split,
                "splitLinesColor": "rgba(255, 255, 255, 0.08)",
                "min": {
                    "type": "constant",
                    "value": min_val,
                    "latestKey": None,
                    "latestKeyType": None,
                    "entityAlias": None,
                    "entityKey": None,
                    "entityKeyType": None
                },
                "max": {
                    "type": "constant",
                    "value": max_val,
                    "latestKey": None,
                    "latestKeyType": None,
                    "entityAlias": None,
                    "entityKey": None,
                    "entityKeyType": None
                }
            }
            if interval is not None:
                ax["interval"] = interval
            if split_number is not None:
                ax["splitNumber"] = split_number
            return ax

        cfg["settings"]["background"] = {
            "type": "color",
            "color": "#121b2d",
            "overlay": {"enabled": False, "color": "rgba(255,255,255,0.72)", "blur": 3}
        }
        cfg["settings"]["legendColumnTitleColor"] = "#ffffff"
        cfg["settings"]["legendColumnTitleFont"] = {"family": "Roboto", "size": 11, "sizeUnit": "px", "style": "normal", "weight": "600", "lineHeight": "1"}
        cfg["settings"]["legendLabelColor"] = "#ffffff"
        cfg["settings"]["legendLabelFont"] = {"family": "Roboto", "size": 12, "sizeUnit": "px", "style": "normal", "weight": "500", "lineHeight": "16px"}
        cfg["settings"]["legendValueColor"] = "#ffffff"
        cfg["settings"]["legendValueFont"] = {"family": "Roboto", "size": 12, "sizeUnit": "px", "style": "normal", "weight": "500", "lineHeight": "16px"}
        cfg["settings"]["tooltipValueColor"] = "#ffffff"
        cfg["settings"]["tooltipDateColor"] = "#ffffff"
        cfg["settings"]["tooltipLabelColor"] = "#ffffff"
        cfg["settings"]["tooltipBackgroundColor"] = "rgba(18, 27, 45, 0.95)"

        if "xAxis" in cfg["settings"]:
            cfg["settings"]["xAxis"]["labelColor"] = "#ffffff"
            cfg["settings"]["xAxis"]["tickLabelColor"] = "#ffffff"
            cfg["settings"]["xAxis"]["lineColor"] = "rgba(255, 255, 255, 0.15)"
            cfg["settings"]["xAxis"]["ticksColor"] = "rgba(255, 255, 255, 0.15)"
            cfg["settings"]["xAxis"]["splitLinesColor"] = "rgba(255, 255, 255, 0.05)"

        cfg["settings"]["yAxes"] = {
            "axis_light": make_axis("axis_light", "Light (ADC)", "#fbbf24", "left", 0, "", 0, show_split=True, min_val=0),
            "axis_dist": make_axis("axis_dist", "Distance (cm)", "#2dd4bf", "left", 1, "cm", 0, min_val=0),
            "axis_temp": make_axis("axis_temp", "Temp (°C)", "#f43f5e", "right", 0, "°C", 1),
            "axis_ai": make_axis("axis_ai", "AI Score", "#818cf8", "right", 1, "", 2, min_val=0, max_val=1, interval=0.2, split_number=5)
        }

        datakeys = []
        for k in keys:
            datakeys.append({
                "name": k["name"],
                "type": "timeseries",
                "label": k["label"],
                "color": k["color"],
                "settings": {
                    "yAxisId": k.get("yAxisId", "default"),
                    "showInLegend": True,
                    "dataHiddenByDefault": False,
                    "type": "line",
                    "lineSettings": {
                        "showLine": True,
                        "step": False,
                        "stepType": "start",
                        "smooth": True,
                        "lineType": "solid",
                        "lineWidth": 2,
                        "showPoints": False
                    }
                },
                "_hash": random.random(),
                "units": k.get("units", ""),
                "decimals": k.get("decimals", 0),
                "aggregationType": None,
                "funcBody": None,
                "usePostProcessing": None,
                "postFuncBody": None
            })

        cfg["datasources"] = [{
            "type": "entity",
            "name": "",
            "entityAliasId": alias_id,
            "dataKeys": datakeys,
            "alarmFilterConfig": {"statusList": ["ACTIVE"]}
        }]
        return {
            "id": wid,
            "typeFullFqn": "system.time_series_chart",
            "type": chart_type,
            "sizeX": 16,
            "sizeY": 6,
            "config": cfg
        }

    def make_btn(wid, title, text, method, params="{}", is_primary=True, bg_color="#1a253b", size_x=4, size_y=2):
        c = copy.deepcopy(rpc_base_cfg)
        c["title"] = title
        c["showTitle"] = False
        c["backgroundColor"] = bg_color
        c["color"] = "#ffffff"
        c["borderRadius"] = "10px"
        c["dropShadow"] = True
        c["targetDevice"] = {"type": "entity", "entityAliasId": alias_id}
        c["targetDeviceAliases"] = []
        c["targetDeviceAlias"] = None
        c["settings"]["requestTimeout"] = 3000
        c["settings"]["oneWayElseTwoWay"] = False
        c["settings"]["buttonText"] = text
        c["settings"]["methodName"] = method
        c["settings"]["methodParams"] = params
        c["settings"]["styleButton"] = {"isRaised": True, "isPrimary": is_primary}
        return {
            "id": wid,
            "typeFullFqn": "system.control_widgets.rpcbutton",
            "type": "rpc",
            "sizeX": size_x,
            "sizeY": size_y,
            "config": c
        }

    def make_history_table(wid):
        c = copy.deepcopy(tbl_base_cfg)
        c["title"] = "Access & Security Audit Log"
        c["showTitle"] = True
        c["titleStyle"] = {"color": "#ffffff", "fontSize": "15px", "fontWeight": "600"}
        c["backgroundColor"] = "#121b2d"
        c["color"] = "#ffffff"
        c["borderRadius"] = "14px"
        c["dropShadow"] = True
        c["widgetCss"] = "th, td, .mat-mdc-header-cell, .mat-header-cell { color: #ffffff !important; opacity: 1 !important; }"

        c["settings"]["showTimestamp"] = True
        c["settings"]["dateFormat"] = {"format": "HH:mm:ss"}
        c["settings"]["displayPagination"] = True
        c["settings"]["defaultPageSize"] = 10
        c["settings"]["enableSearch"] = False
        c["settings"]["enableSelectColumnDisplay"] = False
        c["settings"]["enableStickyHeader"] = True
        c["settings"]["sortOrder"] = {"property": "createdTime", "direction": "DESC"}

        c["datasources"] = [{
            "type": "entity",
            "name": "",
            "entityAliasId": alias_id,
            "dataKeys": [
                {
                    "name": "audit_state",
                    "type": "timeseries",
                    "label": "Door State",
                    "color": "#ffffff",
                    "settings": {
                        "useCellStyleFunction": True,
                        "cellStyleFunction": 'if (value === "UNLOCKED") return {color: "#f59e0b", fontWeight: "bold"}; if (value === "LOCKED") return {color: "#10b981", fontWeight: "bold"}; if (value === "DENIED" || value === "REJECTED" || value === "ALARM" || value === "LOCKDOWN") return {color: "#ef4444", fontWeight: "bold"}; return {color: "#ffffff"};'
                    },
                    "_hash": random.random()
                },
                {
                    "name": "audit_event",
                    "type": "timeseries",
                    "label": "Event / Diagnosis",
                    "color": "#ffffff",
                    "settings": {},
                    "_hash": random.random()
                }
            ]
        }]
        return {
            "id": wid,
            "typeFullFqn": "system.cards.timeseries_table",
            "type": "timeseries",
            "sizeX": 6,
            "sizeY": 6,
            "config": c
        }

    w_temp = "10000000-0000-0000-0000-000000000001"
    w_hum = "10000000-0000-0000-0000-000000000002"
    w_light = "10000000-0000-0000-0000-000000000011"
    w_dist = "10000000-0000-0000-0000-000000000012"
    w_state = "10000000-0000-0000-0000-000000000003"
    w_breach = "10000000-0000-0000-0000-000000000004"
    w_lockdown_state = "10000000-0000-0000-0000-000000000013"
    w_ai = "10000000-0000-0000-0000-000000000010"

    w_chart = "10000000-0000-0000-0000-000000000005"
    w_history = "10000000-0000-0000-0000-000000000015"
    w_unlock = "10000000-0000-0000-0000-000000000006"
    w_lock = "10000000-0000-0000-0000-000000000007"
    w_arm_lockdown = "10000000-0000-0000-0000-000000000009"
    w_clear_lockdown = "10000000-0000-0000-0000-000000000014"
    w_ack = "10000000-0000-0000-0000-000000000008"

    widgets = {
        w_state: make_val(w_state, "Safe Door State", "state", "", 0, "lock", "#10b981", font_size=28, is_func_color=True, color_func='return value === "UNLOCKED" ? "#f59e0b" : "#10b981";'),
        w_temp: make_val(w_temp, "Vault Temperature", "temp", "°C", 1, "thermostat", "#f43f5e"),
        w_hum: make_val(w_hum, "Vault Humidity", "hum", "%", 1, "water_drop", "#38bdf8"),
        w_light: make_val(w_light, "Vault Internal Light", "light_adc", "ADC", 0, "lightbulb", "#fbbf24"),
        w_dist: make_val(w_dist, "Proximity Distance", "distance_cm", "cm", 0, "radar", "#2dd4bf"),
        w_ai: make_val(w_ai, "AI Anomaly Detection Score", "anomaly_score", "", 2, "psychology", "#818cf8"),
        w_breach: make_val(w_breach, "Security Breach Alert", "breach", "", 0, "security", "#10b981", font_size=34, is_func_color=True,
                           color_func='return (value === "BREACH !" || value === true || value === "true" || value === 1) ? "#f43f5e" : "#10b981";',
                           post_func='return (value === true || value === "true" || value === 1) ? "BREACH !" : "SECURE";'),
        w_lockdown_state: make_val(w_lockdown_state, "Lockdown Active", "lockdown", "", 0, "lock_clock", "#10b981", font_size=34, is_func_color=True,
                                   color_func='return (value === "ACTIVE !" || value === true || value === "true" || value === 1) ? "#f43f5e" : "#10b981";',
                                   post_func='return (value === true || value === "true" || value === 1) ? "ACTIVE !" : "NORMAL";'),

        w_chart: make_chart(w_chart, "Live Environmental & Security Telemetry", [
            {"name": "light_adc", "label": "Light Level (ADC)", "color": "#fbbf24", "units": "ADC", "yAxisId": "axis_light"},
            {"name": "distance_cm", "label": "Sonar Distance (cm)", "color": "#2dd4bf", "units": "cm", "yAxisId": "axis_dist"},
            {"name": "temp", "label": "Temperature (°C)", "color": "#f43f5e", "units": "°C", "decimals": 1, "yAxisId": "axis_temp"},
            {"name": "anomaly_score", "label": "AI Anomaly Score", "color": "#818cf8", "decimals": 3, "yAxisId": "axis_ai"}
        ]),

        w_history: make_history_table(w_history),
        w_unlock: make_btn(w_unlock, "Unlock Safe", "🔓 UNLOCK SAFE", "unlock", size_x=3, size_y=2),
        w_lock: make_btn(w_lock, "Lock Safe", "🔒 LOCK SAFE", "lock", size_x=3, size_y=2),
        w_arm_lockdown: make_btn(w_arm_lockdown, "Arm Lockdown", "⛔ ARM LOCKDOWN", "setLockdown", "true", is_primary=True, bg_color="#1a253b", size_x=3, size_y=2),
        w_clear_lockdown: make_btn(w_clear_lockdown, "Clear Lockdown", "🟢 CLEAR LOCKDOWN", "setLockdown", "false", is_primary=True, size_x=3, size_y=2),
        w_ack: make_btn(w_ack, "Acknowledge Alarm", "🛡️ ACKNOWLEDGE ALARM", "ack", size_x=6, size_y=2)
    }

    layout_widgets = {
        w_state: {"sizeX": 3, "sizeY": 4, "row": 0, "col": 0, "mobileOrder": 1, "mobileHeight": 4},
        w_temp: {"sizeX": 3, "sizeY": 4, "row": 0, "col": 3, "mobileOrder": 2, "mobileHeight": 4},
        w_hum: {"sizeX": 3, "sizeY": 4, "row": 0, "col": 6, "mobileOrder": 3, "mobileHeight": 4},
        w_light: {"sizeX": 3, "sizeY": 4, "row": 0, "col": 9, "mobileOrder": 4, "mobileHeight": 4},
        w_dist: {"sizeX": 3, "sizeY": 4, "row": 0, "col": 12, "mobileOrder": 5, "mobileHeight": 4},
        w_ai: {"sizeX": 3, "sizeY": 4, "row": 0, "col": 15, "mobileOrder": 6, "mobileHeight": 4},
        w_breach: {"sizeX": 3, "sizeY": 4, "row": 0, "col": 18, "mobileOrder": 7, "mobileHeight": 4},
        w_lockdown_state: {"sizeX": 3, "sizeY": 4, "row": 0, "col": 21, "mobileOrder": 8, "mobileHeight": 4},

        w_chart: {"sizeX": 12, "sizeY": 6, "row": 4, "col": 0, "mobileOrder": 9, "mobileHeight": 6},
        w_history: {"sizeX": 6, "sizeY": 6, "row": 4, "col": 12, "mobileOrder": 10, "mobileHeight": 6},
        w_unlock: {"sizeX": 3, "sizeY": 2, "row": 4, "col": 18, "mobileOrder": 11, "mobileHeight": 2},
        w_lock: {"sizeX": 3, "sizeY": 2, "row": 4, "col": 21, "mobileOrder": 12, "mobileHeight": 2},
        w_arm_lockdown: {"sizeX": 3, "sizeY": 2, "row": 6, "col": 18, "mobileOrder": 13, "mobileHeight": 2},
        w_clear_lockdown: {"sizeX": 3, "sizeY": 2, "row": 6, "col": 21, "mobileOrder": 14, "mobileHeight": 2},
        w_ack: {"sizeX": 6, "sizeY": 2, "row": 8, "col": 18, "mobileOrder": 15, "mobileHeight": 2}
    }

    # Minimalist, clean, production dashboard configuration
    dashboard_config = {
        "title": "Smart Safe Guardian Dashboard",
        "configuration": {
            "description": "Multi-Node IoT Security Safe Dashboard - HCMUT CO3037",
            "widgets": widgets,
            "states": {
                "default": {
                    "name": "Smart Safe Vault - Security Operations Center",
                    "root": True,
                    "layouts": {
                        "main": {
                            "widgets": layout_widgets,
                            "gridSettings": {
                                "backgroundColor": "#0b0f19",
                                "columns": 24,
                                "margin": 10,
                                "outerMargin": True,
                                "autoFillHeight": False,
                                "mobileAutoFillHeight": False,
                                "mobileRowHeight": 70,
                                "layoutType": "default"
                            }
                        }
                    }
                }
            },
            "entityAliases": {
                alias_id: {
                    "id": alias_id,
                    "alias": "Smart Safe Vault",
                    "filter": {
                        "type": "singleEntity",
                        "singleEntity": {
                            "entityType": "DEVICE",
                            "id": vault_device_id
                        }
                    }
                }
            },
            "timewindow": {
                "displayValue": "",
                "selectedTab": 0,
                "realtime": {
                    "realtimeType": 0,
                    "interval": 1000,
                    "timewindowMs": 300000
                }
            },
            "settings": {
                "stateControllerId": "entity",
                "showTitle": False,
                "showDashboardsSelect": False,
                "showEntitiesSelect": False,
                "showDashboardTimewindow": True,
                "showDashboardExport": True,
                "toolbarAlwaysOpen": True,
                "titleColor": "#ffffff",
                "dashboardCss": (
                    "th.mat-mdc-header-cell, th.mat-header-cell, .tb-time-series-chart-widget th, .tb-legend-header, .legend-header { color: #ffffff !important; opacity: 1 !important; }\n"
                    ".mat-mdc-tooltip, .mat-tooltip, .tb-tooltip, .tb-time-series-chart-tooltip, .tb-chart-tooltip, .echarts-tooltip, .tooltip, div[class*='tooltip'], div[class*='tooltip'] *, .mat-mdc-tooltip .mdc-tooltip__surface, .tb-time-series-chart-tooltip * { color: #ffffff !important; }\n"
                    ".mat-mdc-tooltip .mdc-tooltip__surface, .tb-time-series-chart-tooltip, .echarts-tooltip { background-color: rgba(18, 27, 45, 0.95) !important; border: 1px solid rgba(255, 255, 255, 0.15) !important; }"
                )
            },
            "widgetsCss": (
                "th.mat-mdc-header-cell, th.mat-header-cell, .tb-time-series-chart-widget th, .tb-legend-header, .legend-header { color: #ffffff !important; opacity: 1 !important; }\n"
                ".mat-mdc-tooltip, .mat-tooltip, .tb-tooltip, .tb-time-series-chart-tooltip, .tb-chart-tooltip, .echarts-tooltip, .tooltip, div[class*='tooltip'], div[class*='tooltip'] *, .mat-mdc-tooltip .mdc-tooltip__surface, .tb-time-series-chart-tooltip * { color: #ffffff !important; }\n"
                ".mat-mdc-tooltip .mdc-tooltip__surface, .tb-time-series-chart-tooltip, .echarts-tooltip { background-color: rgba(18, 27, 45, 0.95) !important; border: 1px solid rgba(255, 255, 255, 0.15) !important; }"
            )
        }
    }

    # Check if dashboard already exists
    resp = requests.get(f"{TB_URL}/api/tenant/dashboards?pageSize=50&page=0", headers=headers)
    dash_id = None
    if resp.status_code == 200:
        for d in resp.json().get("data", []):
            if d.get("title") == "Smart Safe Guardian Dashboard":
                dash_id = d["id"]["id"]
                break

    if dash_id:
        dashboard_config["id"] = {"entityType": "DASHBOARD", "id": dash_id}
        save_resp = requests.post(f"{TB_URL}/api/dashboard", headers=headers, json=dashboard_config)
    else:
        save_resp = requests.post(f"{TB_URL}/api/dashboard", headers=headers, json=dashboard_config)
        if save_resp.status_code == 200:
            dash_id = save_resp.json()["id"]["id"]

    return dash_id


def main():
    print("===================================================================")
    print("  Smart Safe Guardian - ThingsBoard Automated Provisioning Script  ")
    print("===================================================================")

    # 1. Connect to sysadmin
    print(f"[*] Checking connection to ThingsBoard at {TB_URL}...")
    sys_token = login(SYSADMIN_USER, SYSADMIN_PASS)
    if not sys_token:
        print(f"[!] Could not login as {SYSADMIN_USER}. Make sure ThingsBoard is running (make up).")
        sys.exit(1)
    print("[+] Sysadmin authenticated.")

    # 2. Tenant
    print(f"[*] Configuring Tenant '{TENANT_TITLE}'...")
    tenant_id = get_or_create_tenant(sys_token)
    print(f"[+] Tenant ready (ID: {tenant_id}).")

    # 3. Tenant Admin
    print(f"[*] Configuring Tenant Administrator '{TENANT_ADMIN_EMAIL}'...")
    ensure_tenant_admin(sys_token, tenant_id)
    tenant_token = login(TENANT_ADMIN_EMAIL, TENANT_ADMIN_PASS)
    if not tenant_token:
        print("[!] Could not authenticate as tenant admin.")
        sys.exit(1)
    print("[+] Tenant Administrator ready.")

    # 4. Devices
    print(f"[*] Registering Vault Device '{DEVICE_NAME}' (Token: {DEVICE_TOKEN})...")
    vault_dev_id = ensure_device(tenant_token, DEVICE_NAME, DEVICE_TOKEN, is_gateway=False)
    print(f"[+] Vault Device ready (ID: {vault_dev_id}).")

    print(f"[*] Registering Gateway Device '{GATEWAY_NAME}'...")
    ensure_device(tenant_token, GATEWAY_NAME, "GATEWAY_SECRET_TOKEN", is_gateway=True)
    print("[+] Gateway Device ready.")

    # 5. Dashboard
    print("[*] Deploying Smart Safe Guardian Dashboard...")
    dash_id = build_and_upload_dashboard(tenant_token, vault_dev_id)
    print(f"[+] Dashboard deployed successfully (ID: {dash_id}).")

    print("\n===================================================================")
    print("                    SETUP COMPLETED SUCCESSFULLY !                 ")
    print("===================================================================")
    print(f"  Web Dashboard URL : {TB_URL}/dashboards/{dash_id}")
    print(f"  Tenant Login      : {TENANT_ADMIN_EMAIL}")
    print(f"  Tenant Password   : {TENANT_ADMIN_PASS}")
    print(f"  Device Token      : {DEVICE_TOKEN}")
    print("===================================================================")


if __name__ == "__main__":
    main()
