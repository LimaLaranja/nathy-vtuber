# 🌸 Nathy VTuber - Deploy no Render (GRÁTIS)

## 🚀 Passo a Passo - Configuração no Render

### 1. **Preparar Repositório GitHub**
```bash
# Se ainda não tiver no GitHub
git init
git add .
git commit -m "Nathy VTuber - Ready for Render"
git branch -M main
git remote add origin https://github.com/seu-usuario/nathy-vtuber.git
git push -u origin main
```

### 2. **Criar Conta Render**
1. Acesse: https://render.com
2. Clique "Sign Up"
3. Conecte com GitHub (grátis)

### 3. **Criar Novo Web Service**
1. Dashboard → "New +" → "Web Service"
2. Conecte seu repositório `nathy-vtuber`
3. Configure:

**Build Settings:**
- **Build Command:** `pip install -r requirements_render.txt`
- **Start Command:** `uvicorn main:app --host 0.0.0.0 --port $PORT`

**Environment:**
- **Runtime:** Python 3
- **Branch:** main
- **Root Directory:** (deixe em branco)

### 4. **Configurar Variáveis de Ambiente**
Na seção "Environment" do service:

```
ENVIRONMENT=production
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-sua-chave-openai-aqui
DEBUG=false
```

### 5. **Deploy Automático**
- Render detecta os arquivos
- Build automático
- Deploy em ~2 minutos
- URL: `https://nathy-vtuber.onrender.com`

---

## ⚙️ Arquivos Criados

### `render.yaml`
- Configuração do service Render
- Plano free configurado
- Variáveis de ambiente

### `requirements_render.txt`
- Dependências otimizadas para nuvem
- Sem dependências pesadas
- Apenas essencial

### `Dockerfile.render`
- Docker otimizado para Render
- Health check incluído
- Build rápido

---

## 🔧 Configurações Importantes

### **WebSocket no Render**
✅ Render suporta WebSocket nativamente  
✅ Funciona com FastAPI + WebSockets  
✅ Sem configuração extra  

### **Plano Free Render**
- ✅ **750 horas/mês** (suficiente para 24/7)
- ✅ **SSL gratuito**
- ✅ **Custom domain**
- ⚠️ **Dorme após 15min inatividade**

### **Manter Awake (Truque)**
```python
# Já adicionado no main.py
@app.get("/ping")
async def ping():
    return {"status": "awake"}

# Use cron job ou UptimeRobot:
# https://nathy-vtuber.onrender.com/ping
# A cada 5 minutos
```

---

## 🌐 Acesso Após Deploy

### **URL Principal:**
```
https://nathy-vtuber.onrender.com
```

### **Interface Nathy:**
```
https://nathy-vtuber.onrender.com/static/nathy_interface.html
```

### **API Docs:**
```
https://nathy-vtuber.onrender.com/docs
```

---

## 💡 Dicas Importantes

### **Performance no Free Tier:**
- Primeiro acesso pode demorar 30s (cold start)
- Use UptimeRobot para manter awake
- Cache Redis se precisar (pago)

### **Monitoramento:**
- Render dashboard mostra logs
- Métricas de uso em tempo real
- Deploy automático a cada push

### **Escalabilidade:**
- Se precisar mais, upgrade para plano pago ($7/mês)
- Mais recursos, sem sleep
- Domínio personalizado

---

## 🎯 Resultado Final

**Nathy VTuber Online Grátis:**
- ✅ URL profissional
- ✅ WebSocket funcionando
- ✅ OpenAI integrado
- ✅ Deploy automático
- ✅ $0/mês

**Pronta para usar!** 🌸✨
