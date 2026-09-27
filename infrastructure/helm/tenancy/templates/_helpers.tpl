{{/*
Common labels applied to every resource in this chart.
*/}}
{{- define "tenancy.labels" -}}
app.kubernetes.io/name: {{ .Chart.Name }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end -}}

{{/*
Selector labels for the Tenancy API Deployment/Service.
*/}}
{{- define "tenancy.api.selectorLabels" -}}
app.kubernetes.io/name: {{ .Chart.Name }}
app.kubernetes.io/component: api
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{/*
Selector labels for the OTel Collector Deployment/Service.
*/}}
{{- define "tenancy.otelCollector.selectorLabels" -}}
app.kubernetes.io/name: {{ .Chart.Name }}
app.kubernetes.io/component: otel-collector
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}
