# import torch
# import torch.nn as nn
# import torch.optim as optim
# from torchvision import datasets, transforms
# from torch.utils.data import DataLoader

# # ==========================
# # Device
# # ==========================
# device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
# print("Using device:", device)

# # ==========================
# # Transform
# # ==========================
# transform = transforms.Compose([
#     transforms.Resize((128,128)),
#     transforms.ToTensor()
# ])
# # transform = transforms.Compose([
# #     transforms.Resize((128,128)),
# #     transforms.ToTensor()
# # ])

# # ==========================
# # Load Dataset
# # ==========================
# train_data = datasets.ImageFolder("dataset/train", transform=transform)
# test_data = datasets.ImageFolder("dataset/test", transform=transform)

# train_loader = DataLoader(train_data, batch_size=16, shuffle=True)
# test_loader = DataLoader(test_data, batch_size=16, shuffle=False)

# print("Classes:", train_data.classes)
# print("Total Classes:", len(train_data.classes))

# # ==========================
# # CNN Model
# # ==========================
# class CNN(nn.Module):
#     def __init__(self):
#         super().__init__()

#         self.conv = nn.Sequential(
#             nn.Conv2d(3, 32, 3, padding=1),
#             nn.ReLU(),
#             nn.MaxPool2d(2),

#             nn.Conv2d(32, 64, 3, padding=1),
#             nn.ReLU(),
#             nn.MaxPool2d(2),

#             nn.Conv2d(64, 128, 3, padding=1),
#             nn.ReLU(),
#             nn.MaxPool2d(2),

#             nn.AdaptiveAvgPool2d((1,1))
#         )

#         self.fc = nn.Sequential(
#             nn.Flatten(),
#             nn.Linear(128, 128),
#             nn.ReLU(),
#             nn.Linear(128, 4)
#         )

#     def forward(self, x):
#         x = self.conv(x)
#         x = self.fc(x)
#         return x
# model = CNN().to(device)

# # ==========================
# # Loss & Optimizer
# # ==========================
# criterion = nn.CrossEntropyLoss()
# optimizer = optim.Adam(model.parameters(), lr=0.001)

# # ==========================
# # Training
# # ==========================
# epochs = 10

# for epoch in range(epochs):
#     model.train()
#     total_loss = 0
#     correct = 0
#     total = 0

#     for images, labels in train_loader:
#         images, labels = images.to(device), labels.to(device)

#         optimizer.zero_grad()
#         outputs = model(images)
#         loss = criterion(outputs, labels)
#         loss.backward()
#         optimizer.step()

#         total_loss += loss.item()

#         _, predicted = torch.max(outputs, 1)
#         correct += (predicted == labels).sum().item()
#         total += labels.size(0)

#     accuracy = 100 * correct / total
#     print(f"Epoch {epoch+1}/{epochs} | Loss: {total_loss:.4f} | Accuracy: {accuracy:.2f}%")

# print("Training Completed ✅")

# # ==========================
# # Save Model
# # ==========================
# torch.save(model.state_dict(), "streetlight_multiclass.pth")
# print("Model saved as streetlight_multiclass.pth ✅")
# ----------------------------------------------------
import torch
import torch.nn as nn
import torch.optim as optim
from torchvision import datasets, transforms
from torch.utils.data import DataLoader

# ==========================
# Device
# ==========================
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print("Using device:", device)

# ==========================
# Transform (IMPORTANT: SAME FOR TRAIN & TEST)
# ==========================
transform = transforms.Compose([
    transforms.Resize((128,128)),
    transforms.ToTensor(),
    transforms.Normalize(
        mean=[0.485, 0.456, 0.406],
        std=[0.229, 0.224, 0.225]
    )
])

# ==========================
# Load Dataset
# ==========================
train_data = datasets.ImageFolder("dataset/train", transform=transform)
test_data = datasets.ImageFolder("dataset/test", transform=transform)

train_loader = DataLoader(train_data, batch_size=16, shuffle=True)
test_loader = DataLoader(test_data, batch_size=16, shuffle=False)

print("Classes:", train_data.classes)
print("Total Classes:", len(train_data.classes))

# Save class names (VERY IMPORTANT)
class_names = train_data.classes
print("Class Order:", class_names)

# ==========================
# CNN Model
# ==========================
class CNN(nn.Module):
    def __init__(self):
        super().__init__()

        self.conv = nn.Sequential(
            nn.Conv2d(3, 32, 3, padding=1),
            nn.BatchNorm2d(32),
            nn.ReLU(),
            nn.MaxPool2d(2),

            nn.Conv2d(32, 64, 3, padding=1),
            nn.BatchNorm2d(64),
            nn.ReLU(),
            nn.MaxPool2d(2),

            nn.Conv2d(64, 128, 3, padding=1),
            nn.BatchNorm2d(128),
            nn.ReLU(),
            nn.MaxPool2d(2),

            nn.AdaptiveAvgPool2d((1,1))
        )

        self.fc = nn.Sequential(
            nn.Flatten(),
            nn.Linear(128, 128),
            nn.ReLU(),
            nn.Dropout(0.5),
            nn.Linear(128, len(class_names))
        )

    def forward(self, x):
        x = self.conv(x)
        x = self.fc(x)
        return x

model = CNN().to(device)

# ==========================
# Loss & Optimizer
# ==========================
criterion = nn.CrossEntropyLoss()
optimizer = optim.Adam(model.parameters(), lr=0.001)

# ==========================
# Training
# ==========================
epochs = 10

for epoch in range(epochs):
    model.train()
    total_loss = 0
    correct = 0
    total = 0

    for images, labels in train_loader:
        images, labels = images.to(device), labels.to(device)

        optimizer.zero_grad()
        outputs = model(images)

        loss = criterion(outputs, labels)
        loss.backward()
        optimizer.step()

        total_loss += loss.item()

        _, predicted = torch.max(outputs, 1)
        correct += (predicted == labels).sum().item()
        total += labels.size(0)

    accuracy = 100 * correct / total
    print(f"Epoch {epoch+1}/{epochs} | Loss: {total_loss:.4f} | Train Accuracy: {accuracy:.2f}%")

# ==========================
# Testing (VERY IMPORTANT)
# ==========================
model.eval()
correct = 0
total = 0

with torch.no_grad():
    for images, labels in test_loader:
        images, labels = images.to(device), labels.to(device)

        outputs = model(images)
        _, predicted = torch.max(outputs, 1)

        correct += (predicted == labels).sum().item()
        total += labels.size(0)

test_accuracy = 100 * correct / total
print(f"Test Accuracy: {test_accuracy:.2f}%")

print("Training Completed ✅")

# ==========================
# Save Model + Classes
# ==========================
torch.save({
    'model_state': model.state_dict(),
    'class_names': class_names
}, "streetlight_multiclass.pth")

print("Model saved with class names ✅")