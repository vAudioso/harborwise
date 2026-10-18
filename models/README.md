# models/

Trained models, one set per segment (`liner` = container and cruise, `other` = tanker, bulk, general cargo).

| File | What it predicts |
|---|---|
| `turnaround_<segment>` | How long a ship will stay, predicted when it berths |
| `regressor_<segment>` | Hours left while a ship is alongside |
| `quantile_<segment>` | The 25/50/90% times until the berth clears |
| `classifier_<segment>` | The chance the berth clears within 6 hours |

- `.json` files hold each model's settings and validation scores, and are kept in git.
- `.joblib` files are the models themselves. They're too large for git: get them with `make download-models`, or train them with `make pipeline`.
