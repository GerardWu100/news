---
title: "Recherche de nouvelles historiques sur les marchés"
description: "Un outil de nouvelles historiques avec deux fonctions : entraîner l'intuition de marché et fournir des données limitées dans le temps aux backtests d'agents IA."
date: 2026-08-12
image: images/historical-market-news-search.png
categories: ["Quantitative Research", "Artificial Intelligence", "Computer Science"]
---

# Recherche de nouvelles historiques sur les marchés

Ce projet remplit deux fonctions :

1. **Entraîner l'intuition de marché.** Une personne choisit une période passée, lit uniquement les nouvelles disponibles pendant cette période, note une prévision de marché, puis vérifie le résultat ultérieur.
2. **Fournir des nouvelles aux backtests d'agents IA.** Un agent d'intelligence artificielle (IA) reçoit les mêmes données limitées dans le temps, produit une prévision et transmet celle-ci à un backtest de stratégie séparé.

Le code source et les instructions d'installation se trouvent dans le [Historical Market News Search GitHub repository](https://github.com/GerardWu100/news).

![Historical Market News Search browser](images/historical-market-news-search.png)

L'interface web présente les deux fonctions dès le début. L'utilisateur choisit ensuite un sujet, une date de début, une date de fin, les sources de nouvelles, la langue et les filtres.

## Ce que fait le projet

Historical Market News Search récupère les articles publiés dans une période inclusive. La même recherche est accessible dans un navigateur, avec l'interface en ligne de commande (CLI) `news-search` et par une interface de programmation d'application HTTP (API).

Le service effectue le travail de préparation nécessaire aux deux méthodes de recherche :

- Interroger plusieurs fournisseurs en parallèle.
- Convertir leurs différentes réponses dans un même format d'article.
- Appliquer des filtres de date, de langue, d'expression, de terme, de domaine, de section et de source.
- Supprimer, sur demande, les adresses identiques et les copies évidentes publiées le même jour.
- Renvoyer un rapport pour chaque source, y compris les pannes et les recherches sans résultat.

Les résultats peuvent être téléchargés en CSV ou en JSON depuis le navigateur. La CLI accepte aussi un tableau lisible, JSON Lines et SQLite. Le format JSON Lines place un enregistrement JSON sur chaque ligne, ce qui facilite le traitement de nombreux articles par un agent.

Le projet récupère et exporte des données. Il ne résume pas les articles, n'appelle pas de modèle de langage, ne calcule pas les rendements, ne crée pas de positions et n'exécute pas de backtest.

## Sources de nouvelles et API

Le service se connecte à six fournisseurs de nouvelles :

- **GDELT Project :** un index mondial ouvert qui ne demande aucune clé API.
- **The New York Times Article Search API :** les archives de l'éditeur, accessibles avec `NYT_API_KEY`.
- **The Guardian Open Platform et NewsAPI :** une API d'éditeur et une API d'agrégation, accessibles avec `GUARDIAN_API_KEY` et `NEWSAPI_API_KEY`.
- **MediaCloud API :** une base de données de recherche sur les médias, accessible avec `MEDIACLOUD_API_KEY` et des collections configurées.
- **ACLED API :** des données sur les conflits et les manifestations, accessibles avec OAuth, une norme d'autorisation utilisée pour obtenir temporairement un jeton d'accès.

Google Trends reste séparé des fournisseurs d'articles. Il mesure l'intérêt relatif des recherches pour les mêmes mots et les mêmes dates dans le navigateur, avec la commande `news-trends` et par `GET /api/trends/interest`.

Chaque fournisseur couvre une partie différente de l'actualité. Ajouter des sources améliore la couverture, mais ne supprime pas les biais géographiques, éditoriaux, linguistiques ou liés aux archives. La réponse conserve la source de chaque article afin que la recherche puisse mesurer ces différences.

## Première fonction : entraîner l'intuition de marché

L'intuition de marché est la capacité à formuler une opinion claire et vérifiable à partir d'informations incomplètes. L'interface web transforme cette compétence en exercice répétable :

1. Choisir une entreprise, un sujet de marché et une période historique.
2. Lire les articles renvoyés et vérifier quelles sources ont réussi ou échoué.
3. Noter une prévision, son horizon, le niveau de confiance et les faits qui l'invalideraient.
4. Révéler le résultat de marché ultérieur et évaluer la prévision sans réécrire l'opinion initiale.

Par exemple, un chercheur peut s'arrêter à une ancienne date de publication de résultats financiers, lire uniquement les 30 jours précédents et prévoir les cinq séances suivantes avant d'ouvrir le graphique des prix. La répétition révèle des habitudes que la lecture rétrospective masque, comme donner trop de poids à un article marquant ou considérer plusieurs copies d'une même dépêche comme des confirmations indépendantes.

Google Trends ajoute un deuxième regard sur l'environnement informationnel. Les articles montrent ce que les éditeurs ont publié; l'intérêt de recherche montre ce que le public cherchait pendant la même période.

## Deuxième fonction : fournir les données d'un backtest de stratégie par agent IA

La méthode automatisée utilise la CLI ou l'API HTTP plutôt que le navigateur. À chaque date de décision historique, un agent IA externe reçoit uniquement la période de nouvelles autorisée. L'agent produit une prévision, tandis qu'un backtest séparé applique les règles de trading et mesure le résultat ultérieur.

Un test valide doit conserver la requête, les dates, la réponse brute, les rapports de sources, le modèle, le prompt et la prévision de chaque décision. Il doit aussi retarder toute transaction simulée jusqu'au moment où les nouvelles auraient réellement pu être collectées, traitées et utilisées.

La séparation entre la collecte, l'agent et le backtest facilite le diagnostic des erreurs. Un article manquant est un problème de données. Une prévision sans fondement est un problème d'agent. Une exécution impossible ou l'absence de coûts de transaction est un problème de backtest.

## Ce que la date limite ne peut pas garantir

La date de fin réduit le biais d'anticipation, c'est-à-dire l'utilisation accidentelle d'informations futures dans une décision historique. Elle ne peut pas éliminer ce risque à elle seule.

Un article peut avoir été modifié après sa publication. Une archive peut être incomplète. La date d'un fournisseur peut différer du moment où un trader pouvait agir. Un modèle de langage peut connaître le résultat ultérieur grâce à ses données d'entraînement. Google Trends remet aussi chaque requête à l'échelle selon son propre sommet; la date de décision facultative supprime donc les observations ultérieures et recalcule les valeurs restantes avec les informations disponibles à cette date.

Ces limites comptent surtout pour la méthode automatisée. Un backtest sérieux doit conserver chaque réponse historique, laisser intacte la période d'évaluation finale, consigner chaque variation du prompt ou de la stratégie et représenter un délai réaliste entre l'information et l'exécution.

Historical Market News Search fournit les nouvelles datées, la couverture des sources, les filtres et les exportations nécessaires à ces deux méthodes. La personne ou l'agent IA formule la prévision; le projet garde la période d'information visible et reproductible.
