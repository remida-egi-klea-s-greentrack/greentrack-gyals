variable "name_prefix" {
  description = "Prefix for every resource name (our group name), e.g. g2-greentrack"
  type        = string
}

variable "jobs_dir" {
  description = "Folder with the pipeline scripts, relative to where terraform runs"
  type        = string
  default     = "../data/jobs"
}

variable "glue_worker_type" {
  description = "Glue worker size. G.1X is the smallest Spark worker."
  type        = string
  default     = "G.1X"
}

variable "glue_number_of_workers" {
  description = "Number of Glue workers per job (2 is the minimum for Spark jobs)"
  type        = number
  default     = 2
}

variable "raw_file_name" {
  description = "Default raw file the bronze job reads from the bronze bucket's incoming/ folder"
  type        = string
  default     = "household_power_consumption.txt"
}



