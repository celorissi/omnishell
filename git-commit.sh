#!/bin/bash

BRANCH="main"
REMOTE="origin"
MENSAGEM=${1:-"Atualização automática"}

# 1. Adiciona e salva suas alterações locais
git add .
git commit -m "$MENSAGEM"

# 2. Baixa as alterações do remoto e aplica seu commit por cima delas
# O parâmetro -X ours faz com que, em caso de conflito na mesma linha, prevaleça a sua versão local
git pull --rebase -X ours $REMOTE $BRANCH

# 3. Envia para o repositório remoto
git push $REMOTE $BRANCH