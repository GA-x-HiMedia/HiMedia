from faker import Faker
import random, json, csv
from pathlib import Path

fake = Faker()
Faker.seed(42)
random.seed(42)

NUM_USERS = 250
NUM_PROJECTS = 75
NUM_TASKS = 10000

roles = ["owner", "manager", "creator_editor", "viewer"]
statuses = ["todo", "in_progress", "in_review", "done"]
priorities = ["low", "medium", "high", "urgent"]

users = []
for i in range(NUM_USERS):
    role = random.choices(roles, weights=[2, 12, 56, 30], k=1)[0]
    users.append({
        "id": f"usr_{i+1:04d}",
        "name": fake.name(),
        "email": fake.unique.email(),
        "role": role,
        "active": random.random() > 0.04
    })

projects = []
for i in range(NUM_PROJECTS):
    projects.append({
        "id": f"prj_{i+1:03d}",
        "name": fake.catch_phrase(),
        "client_name": fake.company(),
        "archived": random.random() < 0.08
    })

tasks = []
for i in range(NUM_TASKS):
    assignee = random.choice(users)
    project = random.choice(projects)
    tasks.append({
        "id": f"tsk_{i+1:05d}",
        "project_id": project["id"],
        "title": fake.sentence(nb_words=random.randint(3, 8)).rstrip("."),
        "status": random.choices(statuses, weights=[25, 30, 20, 25], k=1)[0],
        "priority": random.choices(priorities, weights=[15, 50, 25, 10], k=1)[0],
        "client_visible": random.choice([True, False]),
        "assignee_id": assignee["id"],
        "assignee_name": assignee["name"],
        "assignee_email": assignee["email"],
        "created_at": fake.date_time_between(start_date="-1y", end_date="now").isoformat(),
        "description": fake.paragraph(nb_sentences=random.randint(1, 3))
    })

out = Path("sandbox_data")
out.mkdir(exist_ok=True)

for name, data in [("users.json", users), ("projects.json", projects), ("tasks.json", tasks)]:
    with open(out / name, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

with open(out / "tasks.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=tasks[0].keys())
    writer.writeheader()
    writer.writerows(tasks)

print(f"Generated {NUM_USERS} users, {NUM_PROJECTS} projects, and {NUM_TASKS} tasks.")
