# I Built MeritRank: An Explainable AI Shortlist Engine for Hiring

Hiring search still breaks in a surprisingly ordinary way: a recruiter writes
a nuanced job description, but the search tool reduces it to a bag of
keywords. Strong candidates can disappear because their profiles use different
phrasing. Other candidates rise to the top because they repeated the right
terms.

For the INDIA.RUNS challenge, I built **MeritRank**, a working candidate-ranking
service focused on a simple question:

> Can we produce a better shortlist while showing recruiters exactly why each
> person was recommended?

## What the service does

MeritRank accepts a job description and a pool of candidate profiles. It
returns a ranked shortlist with:

- matched required skills,
- missing hard requirements,
- preferred skills,
- role and experience fit,
- bounded activity signals,
- and a human-readable explanation for every score.

The first working version uses a transparent two-stage pipeline. BM25 retrieval
measures contextual relevance across the profile. A structured reranker then
combines required-skill coverage, preferred skills, role similarity,
experience, location preferences, and recent activity.

## Responsible ranking matters

A ranking system should not quietly learn shortcuts from personal information.
MeritRank deliberately excludes names, emails, phone numbers, and protected
attributes from scoring. The recruiter can still see the candidate identity
when reviewing a shortlist, but identity is not evidence of fit.

The engine also exposes gaps. If a candidate is missing a required skill, the
system says so. AI should help a recruiter inspect evidence, not hide judgment
behind an unexplained number.

## What is real today

The repository contains a runnable API, a browser dashboard, a CSV exporter,
automated tests, and a clearly labeled synthetic dataset. It works locally with
the Python standard library, so anyone can run the baseline without API keys.

I am not claiming benchmark improvements yet. The official challenge dataset
is still needed for honest measurement.

## What comes next

With the official dataset, I will evaluate precision@10, recall@10, NDCG@10,
latency, and fairness slices. Multilingual embeddings and learned reranking
will only be added if the numbers show a measurable improvement over the
transparent baseline.

The goal is not to replace recruiters. It is to make the first shortlist more
relevant, more inspectable, and easier to trust.

#IndiaRuns #ArtificialIntelligence #HiringTech #MachineLearning #Search

