"""Collecte des erreurs et avertissements, avec l'emplacement de la donnée fautive."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Issue:
    level: str          # error | warning | info
    code: str           # identifiant stable, ex. REF_UNKNOWN
    message: str
    where: str = ""     # fichier (et ligne/colonne si connues)


@dataclass
class Issues:
    items: list = field(default_factory=list)

    def error(self, code, message, where=""):
        self.items.append(Issue("error", code, message, where))

    def warning(self, code, message, where=""):
        self.items.append(Issue("warning", code, message, where))

    def info(self, code, message, where=""):
        self.items.append(Issue("info", code, message, where))

    @property
    def errors(self):
        return [i for i in self.items if i.level == "error"]

    @property
    def warnings(self):
        return [i for i in self.items if i.level == "warning"]

    def print(self, max_per_level=200):
        for level, label in (("error", "ERREUR"), ("warning", "AVERTISSEMENT")):
            items = [i for i in self.items if i.level == level]
            for issue in items[:max_per_level]:
                where = f"  [{issue.where}]" if issue.where else ""
                print(f"{label:<13} {issue.code:<22} {issue.message}{where}")
            if len(items) > max_per_level:
                print(f"… et {len(items) - max_per_level} de plus ({label.lower()}s)")
        print(f"{len(self.errors)} erreur(s), {len(self.warnings)} avertissement(s)")
