<?php
include 'config.php';

$token = $_GET['token'];

$res = $conn->query("SELECT * FROM password_resets 
                     WHERE token='$token' AND expires_at > NOW()");

if ($res->num_rows == 0) {
    die("Link expired or invalid");
}

if ($_SERVER["REQUEST_METHOD"] == "POST") {

    $new_pass = password_hash($_POST['password'], PASSWORD_BCRYPT);
    $row = $res->fetch_assoc();
    $email = $row['email'];

    $conn->query("UPDATE admins SET password_hash='$new_pass' WHERE email='$email'");
    $conn->query("DELETE FROM password_resets WHERE email='$email'");

    echo "Password updated";
}
?>