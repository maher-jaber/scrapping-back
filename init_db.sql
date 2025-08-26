-- phpMyAdmin SQL Dump
-- version 5.2.1
-- https://www.phpmyadmin.net/
--
-- Hôte : 127.0.0.1:3306
-- Généré le : mar. 26 août 2025 à 08:35
-- Version du serveur : 9.1.0
-- Version de PHP : 8.3.14

SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
START TRANSACTION;
SET time_zone = "+00:00";


/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8mb4 */;

--
-- Base de données : `railway`
--

-- --------------------------------------------------------

--
-- Structure de la table `scraped_data`
--

DROP TABLE IF EXISTS `scraped_data`;
CREATE TABLE IF NOT EXISTS `scraped_data` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `name` varchar(200) NOT NULL,
  `address` varchar(200) DEFAULT NULL,
  `phone` varchar(50) DEFAULT NULL,
  `website` varchar(255) DEFAULT NULL,
  `plus_code` varchar(100) DEFAULT NULL,
  `note` decimal(3,2) DEFAULT NULL,
  `horaires` text,
  `reviews` varchar(50) DEFAULT NULL,
  `scraped_at` datetime DEFAULT NULL,
  `unique_hash` char(32) DEFAULT NULL,
  `already_scrapped` tinyint DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `unique_hash` (`unique_hash`)
) ENGINE=MyISAM AUTO_INCREMENT=246 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- --------------------------------------------------------

--
-- Structure de la table `scrape_history`
--

DROP TABLE IF EXISTS `scrape_history`;
CREATE TABLE IF NOT EXISTS `scrape_history` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `scraped_data_id` bigint NOT NULL,
  `source` varchar(50) NOT NULL,
  `query` varchar(200) DEFAULT NULL,
  `location` varchar(200) DEFAULT NULL,
  `scraped_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `scraped_data_id` (`scraped_data_id`)
) ENGINE=MyISAM AUTO_INCREMENT=378 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- --------------------------------------------------------

--
-- Structure de la table `users`
--

DROP TABLE IF EXISTS `users`;
CREATE TABLE IF NOT EXISTS `users` (
  `id` int NOT NULL AUTO_INCREMENT,
  `username` varchar(100) NOT NULL,
  `password_hash` varchar(255) NOT NULL,
  `refresh_token` text,
  `refresh_token_expiry` datetime DEFAULT NULL,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `username` (`username`)
) ENGINE=MyISAM AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

--
-- Déchargement des données de la table `users`
--

INSERT INTO `users` (`id`, `username`, `password_hash`, `refresh_token`, `refresh_token_expiry`, `created_at`) VALUES
(1, 'admin', '$2b$12$IMdIhJglcfVF2GMBxgospO/5zIf7Mr8ChDiC8IIZNa.Zm1ktVwQD2', NULL, NULL, '2025-08-21 07:21:49'),
(2, 'admin2', '$2b$12$EXpK...OIFGonUpVEM4xxegrFTRlMWsA0uKFE3dKhPUcVFPF8/PXO', NULL, NULL, '2025-08-21 10:20:35');
COMMIT;

/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
